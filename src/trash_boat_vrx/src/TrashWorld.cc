// Copyright 2026 Abhinav Siddharth
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Simulator-only physics and scoring. No trash poses are exported to the controller.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <map>
#include <string>
#include <gz/msgs/double.pb.h>
#include <gz/msgs/empty.pb.h>
#include <gz/msgs/int32.pb.h>
#include <gz/msgs/odometry.pb.h>
#include <gz/msgs/pose.pb.h>
#include <gz/msgs/Utility.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>
#include "trash_boat_vrx/intake.hh"

namespace trash_boat_vrx
{
class TrashWorld : public gz::sim::System,
                   public gz::sim::ISystemConfigure,
                   public gz::sim::ISystemPreUpdate,
                   public gz::sim::ISystemPostUpdate
{
 public:
  void Configure(const gz::sim::Entity &, const std::shared_ptr<const sdf::Element> &sdf,
                 gz::sim::EntityComponentManager &, gz::sim::EventManager &) override
  {
    current = sdf->Get<double>("current", 0.05).first;
    driftGain = sdf->Get<double>("drift_gain", 3.0).first;
    arm = sdf->Get<double>("thruster_arm", 0.65).first;
    thrustLimit = sdf->Get<double>("thrust_limit", 50.0).first;
    timeout = sdf->Get<double>("command_timeout", 0.5).first;
    publishPeriod = 1.0 / sdf->Get<double>("publish_rate", 20.0).first;
    scoopForward = sdf->Get<double>("scoop_forward", 1.5).first;
    scoopLateral = sdf->Get<double>("scoop_lateral", 1.0).first;
    endX = sdf->Get<double>("canal_length", 60.0).first - 0.5;
    posePub = node.Advertise<gz::msgs::Pose>("/vrx/boat_pose");
    odomPub = node.Advertise<gz::msgs::Odometry>("/vrx/odometry");
    collectedPub = node.Advertise<gz::msgs::Int32>("/vrx/collected");
    remainingPub = node.Advertise<gz::msgs::Int32>("/vrx/remaining");
    hitsPub = node.Advertise<gz::msgs::Int32>("/vrx/bank_hits");
    node.Subscribe("/vrx/collect", &TrashWorld::Collect, this);
    node.Subscribe("/vrx/left_thrust", &TrashWorld::Left, this);
    node.Subscribe("/vrx/right_thrust", &TrashWorld::Right, this);
    gzmsg << "TrashWorld configured: physical forces, explicit scoop, contact scoring\n";
  }

  void PreUpdate(const gz::sim::UpdateInfo &info,
                 gz::sim::EntityComponentManager &ecm) override
  {
    if (info.paused) return;
    const double now = std::chrono::duration<double>(info.simTime).count();
    simNow.store(now);
    if (boat.Entity() == gz::sim::kNullEntity)
    {
      const auto model = ecm.EntityByComponents(gz::sim::components::Model(),
        gz::sim::components::Name("trash_boat"));
      if (model == gz::sim::kNullEntity) return;
      boat = gz::sim::Link(gz::sim::Model(model).LinkByName(ecm, "base_link"));
      boat.EnableVelocityChecks(ecm);
      ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
        [&](const gz::sim::Entity &entity, const auto *, const auto *name)
        {
          if (name->Data().rfind("trash_", 0) == 0 && name->Data() != "trash_boat")
          {
            gz::sim::Link link(gz::sim::Model(entity).LinkByName(ecm, "link"));
            link.EnableVelocityChecks(ecm);
            trash.emplace(entity, link);
          }
          return true;
        });
      gzmsg << "TrashWorld ready with " << trash.size() << " physical trash models\n";
    }
    const auto pose = gz::sim::worldPose(boat.Entity(), ecm);
    const auto forward = pose.Rot().RotateVector(gz::math::Vector3d::UnitX);
    const double l = now - leftAt.load() <= timeout ? left.load() : 0.0;
    const double r = now - rightAt.load() <= timeout ? right.load() : 0.0;
    boat.AddWorldForce(ecm, forward * l, {-0.65, arm, 0});
    boat.AddWorldForce(ecm, forward * r, {-0.65, -arm, 0});
    const bool collect = requested.exchange(false);
    for (auto it = trash.begin(); it != trash.end();)
    {
      const auto location = gz::sim::worldPose(it->second.Entity(), ecm);
      if (collect && InIntake(pose, location.Pos(), scoopForward, scoopLateral))
      {
        ecm.RequestRemoveEntity(it->first);
        it = trash.erase(it);
        ++collected;
        gzmsg << "Scoop collected item; total=" << collected << "\n";
        continue;
      }
      const auto velocity = it->second.WorldLinearVelocity(ecm);
      if (velocity)
      {
        // Water drag acts as a force; no model teleporting or velocity resets.
        const double target = location.Pos().X() < endX ? current : 0.0;
        it->second.AddWorldForce(ecm,
          {driftGain * (target - velocity->X()), -driftGain * velocity->Y(), 0});
      }
      ++it;
    }
  }

  void PostUpdate(const gz::sim::UpdateInfo &info,
                  const gz::sim::EntityComponentManager &ecm) override
  {
    if (info.paused || boat.Entity() == gz::sim::kNullEntity) return;
    bool touching = false;
    ecm.Each<gz::sim::components::ContactSensorData>(
      [&](const gz::sim::Entity &, const auto *data)
      {
        for (const auto &contact : data->Data().contact())
        {
          if ((IsBank(contact.collision1().id(), ecm) ||
               IsBank(contact.collision2().id(), ecm))) touching = true;
        }
        return true;
      });
    if (touching && !inContact) ++bankHits;
    inContact = touching;
    const double now = std::chrono::duration<double>(info.simTime).count();
    if (now - lastPublish < publishPeriod) return;
    lastPublish = now;
    gz::msgs::Pose poseMsg;
    gz::msgs::Set(&poseMsg, gz::sim::worldPose(boat.Entity(), ecm));
    Stamp(poseMsg.mutable_header(), now, "map");
    posePub.Publish(poseMsg);
    gz::msgs::Odometry odom;
    *odom.mutable_header() = poseMsg.header();
    *odom.mutable_pose() = poseMsg;
    const auto lin = boat.WorldLinearVelocity(ecm);
    const auto ang = boat.WorldAngularVelocity(ecm);
    if (lin && ang)
    {
      const auto rotation = gz::sim::worldPose(boat.Entity(), ecm).Rot().Inverse();
      gz::msgs::Set(odom.mutable_twist()->mutable_linear(), rotation.RotateVector(*lin));
      gz::msgs::Set(odom.mutable_twist()->mutable_angular(), rotation.RotateVector(*ang));
    }
    auto *child = odom.mutable_header()->add_data();
    child->set_key("child_frame_id");
    child->add_value("boat");
    odomPub.Publish(odom);
    gz::msgs::Int32 count;
    count.set_data(collected); collectedPub.Publish(count);
    count.set_data(static_cast<int>(trash.size())); remainingPub.Publish(count);
    count.set_data(bankHits); hitsPub.Publish(count);
  }

 private:
  static void Stamp(gz::msgs::Header *header, double time, const std::string &frame)
  {
    const auto sec = static_cast<int64_t>(time);
    header->mutable_stamp()->set_sec(sec);
    header->mutable_stamp()->set_nsec(static_cast<int32_t>((time - sec) * 1e9));
    auto *data = header->add_data();
    data->set_key("frame_id"); data->add_value(frame);
  }
  static bool IsBank(gz::sim::Entity entity,
                     const gz::sim::EntityComponentManager &ecm)
  {
    while (entity != gz::sim::kNullEntity)
    {
      const auto *name = ecm.Component<gz::sim::components::Name>(entity);
      if (name && name->Data().rfind("bank_", 0) == 0) return true;
      const auto *parent = ecm.Component<gz::sim::components::ParentEntity>(entity);
      entity = parent ? parent->Data() : gz::sim::kNullEntity;
    }
    return false;
  }
  void Collect(const gz::msgs::Empty &) { requested.store(true); }
  void Left(const gz::msgs::Double &msg)
  {
    left.store(std::isfinite(msg.data()) ? std::clamp(msg.data(), -thrustLimit, thrustLimit) : 0);
    leftAt.store(simNow.load());
  }
  void Right(const gz::msgs::Double &msg)
  {
    right.store(std::isfinite(msg.data()) ? std::clamp(msg.data(), -thrustLimit, thrustLimit) : 0);
    rightAt.store(simNow.load());
  }
  gz::transport::Node node;
  gz::transport::Node::Publisher posePub, odomPub, collectedPub, remainingPub, hitsPub;
  gz::sim::Link boat{gz::sim::kNullEntity};
  std::map<gz::sim::Entity, gz::sim::Link> trash;
  std::atomic<bool> requested{false};
  std::atomic<double> simNow{0}, left{0}, right{0}, leftAt{-100}, rightAt{-100};
  double current{0.05}, driftGain{3}, arm{0.65}, thrustLimit{50}, timeout{0.5};
  double publishPeriod{0.05}, lastPublish{-1}, scoopForward{1.5}, scoopLateral{1}, endX{59.5};
  int collected{0}, bankHits{0};
  bool inContact{false};
};
}  // namespace trash_boat_vrx
GZ_ADD_PLUGIN(trash_boat_vrx::TrashWorld, gz::sim::System,
  trash_boat_vrx::TrashWorld::ISystemConfigure,
  trash_boat_vrx::TrashWorld::ISystemPreUpdate,
  trash_boat_vrx::TrashWorld::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(trash_boat_vrx::TrashWorld, "trash_boat_vrx::TrashWorld")
