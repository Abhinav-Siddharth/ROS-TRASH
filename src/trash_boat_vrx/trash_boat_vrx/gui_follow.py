# Copyright 2026 Abhinav Siddharth
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Enable Gazebo's configured follow target once its GUI service is ready."""

import subprocess
import sys
from threading import Event
import time


def main() -> None:
    """Activate follow mode explicitly; SDF target loading alone leaves mode NONE."""
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            try:
                result = subprocess.run([
                    'gz', 'service', '-s', '/gui/follow', '--reqtype', 'gz.msgs.StringMsg',
                    '--reptype', 'gz.msgs.Boolean', '--timeout', '1000',
                    '--req', 'data: "trash_boat"',
                ], capture_output=True, text=True, timeout=3, check=False)
                if result.returncode == 0 and 'data: true' in result.stdout:
                    sys.stdout.write('GUI follow camera enabled for trash_boat\n')
                    return
            except subprocess.TimeoutExpired:
                pass
            Event().wait(0.3)
    except KeyboardInterrupt:
        return
    raise SystemExit('Gazebo GUI follow service did not become ready within 60 seconds')


if __name__ == '__main__':
    main()
