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

#ifndef TRASH_BOAT_VRX_INTAKE_HH_
#define TRASH_BOAT_VRX_INTAKE_HH_
#include <cmath>
#include <gz/math/Pose3.hh>
namespace trash_boat_vrx
{
// The scoring frame follows heading; waves must not expand the water-plane intake.
inline bool InIntake(const gz::math::Pose3d &boat, const gz::math::Vector3d &trash,
                     double forward = 1.5, double lateral = 1.0)
{
  const auto delta = trash - boat.Pos();
  const double yaw = boat.Rot().Yaw();
  const double x = std::cos(yaw) * delta.X() + std::sin(yaw) * delta.Y();
  const double y = -std::sin(yaw) * delta.X() + std::cos(yaw) * delta.Y();
  return x >= 0.0 && x <= forward && std::abs(y) <= lateral;
}
}  // namespace trash_boat_vrx
#endif
