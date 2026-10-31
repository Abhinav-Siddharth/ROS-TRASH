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

#include <gtest/gtest.h>
#include "trash_boat_vrx/intake.hh"
TEST(Intake, FrozenBounds)
{
  const gz::math::Pose3d boat(2, 1, 0, 0, 0, 0);
  EXPECT_TRUE(trash_boat_vrx::InIntake(boat, {3, 1, 0.1}));
  EXPECT_TRUE(trash_boat_vrx::InIntake(boat, {3.5, 2, 0.1}));
  EXPECT_FALSE(trash_boat_vrx::InIntake(boat, {3.501, 1, 0.1}));
  EXPECT_FALSE(trash_boat_vrx::InIntake(boat, {3, 2.001, 0.1}));
  EXPECT_FALSE(trash_boat_vrx::InIntake(boat, {1.999, 1, 0.1}));
}
TEST(Intake, RotationAndTranslation)
{
  const gz::math::Pose3d boat(20, -2, 0, 0.1, -0.1, GZ_PI_2);
  EXPECT_TRUE(trash_boat_vrx::InIntake(boat, {20, -1, 0.1}));
  EXPECT_FALSE(trash_boat_vrx::InIntake(boat, {20, 0, 0.1}));
}
