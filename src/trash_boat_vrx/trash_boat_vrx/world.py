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

"""Generate an offline, deterministic canal world using upstream VRX physics."""

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import random
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class WorldConfig:
    """Explicit world settings; the reference acceptance values stay frozen."""

    seed: int = 42
    n_trash: int = 12
    current: float = 0.05
    canal_length: float = 60.0
    half_width: float = 4.0
    wave_amplitude: float = 0.0
    wave_period: float = 5.0
    image_size: int = 400
    camera_height: float = 6.0
    camera_span: float = 10.0
    step_size: float = 0.005
    real_time_factor: float = 1.0
    boat_x: float = 2.0
    boat_y: float = 0.0
    boat_yaw: float = 0.0

    def validate(self) -> None:
        """Reject unsafe or invalid launch values before starting Gazebo."""
        values = [self.current, self.canal_length, self.half_width, self.wave_amplitude,
                  self.wave_period, self.camera_height, self.camera_span, self.step_size,
                  self.real_time_factor, self.boat_x, self.boat_y, self.boat_yaw]
        if not all(math.isfinite(x) for x in values):
            raise ValueError('World parameters must be finite')
        if self.n_trash < 1 or self.image_size < 32:
            raise ValueError('Need at least one trash item and a usable camera')
        if self.canal_length < 12 or self.half_width < 2:
            raise ValueError('Canal is too small for this craft and spawn distribution')
        if min(self.wave_period, self.camera_height, self.camera_span,
               self.step_size, self.real_time_factor) <= 0 or self.wave_amplitude < 0:
            raise ValueError('Rates and dimensions must be positive; waves nonnegative')
        if not 0 < self.boat_x < self.canal_length or abs(self.boat_y) >= self.half_width:
            raise ValueError('Boat must start inside the canal')


def child(parent: ET.Element, tag: str, text: object = None, **attrs) -> ET.Element:
    """Append an SDF element, optionally setting its text."""
    element = ET.SubElement(parent, tag, attrs)
    if text is not None:
        element.text = str(text)
    return element


def plugin(parent: ET.Element, filename: str, name: str, **params) -> ET.Element:
    """Create a system plugin with explicit parameters."""
    element = child(parent, 'plugin', filename=filename, name=name)
    for key, value in params.items():
        child(element, key, value)
    return element


def geometry(parent: ET.Element, kind: str, value: str) -> None:
    """Create a primitive geometry from its compact dimensions."""
    shape = child(child(parent, 'geometry'), kind)
    if kind == 'box':
        child(shape, 'size', value)
    elif kind == 'sphere':
        child(shape, 'radius', value)
    else:
        radius, length = value.split()
        child(shape, 'radius', radius)
        child(shape, 'length', length)


def part(link: ET.Element, name: str, kind: str, value: str, pose: str,
         color: str, collision: bool = True) -> None:
    """Add matching visual/collision geometry without external model assets."""
    visual = child(link, 'visual', name=name)
    child(visual, 'pose', pose)
    geometry(visual, kind, value)
    material = child(visual, 'material')
    child(material, 'ambient', color)
    child(material, 'diffuse', color)
    child(material, 'specular', '0.15 0.15 0.15 1')
    if collision:
        solid = child(link, 'collision', name=name + '_collision')
        child(solid, 'pose', pose)
        geometry(solid, kind, value)


def inertia(link: ET.Element, mass: float, diagonal: tuple[float, float, float]) -> None:
    """Set explicit positive inertial values."""
    inertial = child(link, 'inertial')
    child(inertial, 'mass', mass)
    tensor = child(inertial, 'inertia')
    for tag, value in zip(('ixx', 'iyy', 'izz'), diagonal):
        child(tensor, tag, value)


def waves(parent: ET.Element, config: WorldConfig) -> None:
    """Use the same analytic VRX wave field for craft and floating objects."""
    wave = child(child(parent, 'wavefield'), 'wave')
    for key, value in {'model': 'CWR', 'number': 1, 'amplitude': config.wave_amplitude,
                       'period': config.wave_period, 'direction': 0.4,
                       'steepness': 0.0, 'tau': 2.0}.items():
        child(wave, key, value)


def spawn_positions(config: WorldConfig) -> list[tuple[float, float]]:
    """Use exactly the reference seeded spawn distribution."""
    rng = random.Random(config.seed)
    return [(rng.uniform(8, config.canal_length - 3),
             rng.uniform(-config.half_width + 0.8, config.half_width - 0.8))
            for _ in range(config.n_trash)]


def make_boat(world: ET.Element, config: WorldConfig) -> None:
    """Build a compact catamaran with a visible intake and real camera."""
    model = child(world, 'model', name='trash_boat')
    child(model, 'pose', f'{config.boat_x} {config.boat_y} 0.12 0 0 {config.boat_yaw}')
    link = child(model, 'link', name='base_link')
    inertia(link, 35.0, (8.0, 12.0, 16.0))
    for side, y in [('port', 0.65), ('starboard', -0.65)]:
        part(link, side, 'cylinder', '0.18 1.8',
             f'-0.1 {y} 0 0 {math.pi / 2} 0', '0.12 0.3 0.65 1')
        part(link, side + '_cap', 'sphere', '0.18',
             f'0.8 {y} 0 0 0 0', '0.85 0.9 0.95 1', False)
        part(link, side + '_thruster', 'cylinder', '0.11 0.2',
             f'-1.05 {y} 0 0 {math.pi / 2} 0', '0.08 0.09 0.12 1', False)
    part(link, 'deck', 'box', '1.2 1.5 0.12', '-0.35 0 0.22 0 0 0',
         '0.88 0.92 0.95 1')
    part(link, 'electronics', 'box', '0.45 0.5 0.22', '-0.45 0 0.38 0 0 0',
         '0.1 0.16 0.22 1', False)
    for y in [-1.0, 1.0]:
        part(link, 'intake_' + str(y), 'box', '1.5 0.035 0.08',
             f'0.75 {y} -0.01 0 0 0', '0.25 0.8 0.85 1', False)
    for x in [0.15, 0.4, 0.65, 0.9, 1.15, 1.4]:
        part(link, 'net_' + str(x), 'box', '0.015 2 0.012', f'{x} 0 -0.06 0 0 0',
             '0.2 0.55 0.6 1', False)
    # The camera is a known elevated virtual mount. No mast occludes its image.
    sensor = child(link, 'sensor', name='survey_camera', type='camera')
    child(sensor, 'pose', f'0 0 {config.camera_height} 0 {math.pi / 2} 0')
    child(sensor, 'topic', '/vrx/camera')
    child(sensor, 'update_rate', 10)
    child(sensor, 'always_on', 'true')
    camera = child(sensor, 'camera')
    child(camera, 'horizontal_fov', 2 * math.atan(config.camera_span / 2 / config.camera_height))
    image = child(camera, 'image')
    child(image, 'width', config.image_size)
    child(image, 'height', config.image_size)
    child(image, 'format', 'R8G8B8')
    clip = child(camera, 'clip')
    child(clip, 'near', 0.1)
    child(clip, 'far', 100)
    contact = child(link, 'sensor', name='hull_contact', type='contact')
    child(contact, 'always_on', 'true')
    child(contact, 'update_rate', 100)
    collisions = child(contact, 'contact')
    for name in ['port', 'starboard', 'deck']:
        child(collisions, 'collision', name + '_collision')
    child(collisions, 'topic', '/vrx/hull_contacts')
    surface = plugin(model, 'libSurface.so', 'vrx::Surface', link_name='base_link',
                     hull_length=3.6, hull_radius=0.18, fluid_density=1000,
                     fluid_level=0.0)
    points = child(surface, 'points')
    for x in [-0.65, 0.65]:
        for y in [-0.65, 0.65]:
            child(points, 'point', f'{x} {y} -0.18')
    waves(surface, config)
    plugin(model, 'libSimpleHydrodynamics.so', 'vrx::SimpleHydrodynamics',
           link_name='base_link', xDotU=0.0, yDotV=0.0, zDotW=0.0, kDotP=0.0,
           mDotQ=0.0, nDotR=0.0, xU=20.0, xUU=0.0, yV=50.0, yVV=0.0,
           zW=100.0, zWW=0.0, kP=40.0, kPP=0.0, mQ=40.0, mQQ=0.0, nR=10.0, nRR=0.0)


def make_trash(world: ET.Element, config: WorldConfig) -> None:
    """Create independently floating orange objects; no automatic collection."""
    for index, (x, y) in enumerate(spawn_positions(config)):
        model = child(world, 'model', name=f'trash_{index:02d}')
        child(model, 'pose', f'{x} {y} 0.1 0 0 0')
        link = child(model, 'link', name='link')
        inertia(link, 0.5, (0.006, 0.006, 0.006))
        part(link, 'object', 'sphere', '0.15', '0 0 0 0 0 0', '1 0.5 0 1')
        buoyancy = plugin(model, 'libPolyhedraBuoyancyDrag.so',
                          'vrx::PolyhedraBuoyancyDrag', fluid_density=1000,
                          fluid_level=0.0, linear_drag=2.0, angular_drag=1.0)
        shape = child(buoyancy, 'buoyancy', name='float')
        child(shape, 'link_name', 'link')
        geometry(shape, 'sphere', '0.15')
        waves(buoyancy, config)


def make_world(config: WorldConfig) -> str:
    """Return complete SDF; all geometry is local and no Fuel downloads occur."""
    config.validate()
    root = ET.Element('sdf', version='1.9')
    world = child(root, 'world', name='trash_canal')
    physics = child(world, 'physics', name='water_physics', type='ignored')
    child(physics, 'max_step_size', config.step_size)
    child(physics, 'real_time_factor', config.real_time_factor)
    child(world, 'gravity', '0 0 -9.81')
    for library, name in [('physics', 'Physics'), ('user-commands', 'UserCommands'),
                          ('scene-broadcaster', 'SceneBroadcaster'), ('contact', 'Contact')]:
        plugin(world, 'gz-sim-' + library + '-system', 'gz::sim::systems::' + name)
    plugin(world, 'gz-sim-sensors-system', 'gz::sim::systems::Sensors', render_engine='ogre2')
    scene = child(world, 'scene')
    child(scene, 'ambient', '0.65 0.65 0.65 1')
    child(scene, 'background', '0.55 0.75 0.92 1')
    child(scene, 'shadows', 'false')
    child(scene, 'grid', 'false')
    light = child(world, 'light', name='sun', type='directional')
    child(light, 'pose', '0 0 10 0 0 0')
    child(light, 'diffuse', '0.8 0.8 0.8 1')
    child(light, 'specular', '0.2 0.2 0.2 1')
    child(light, 'direction', '-0.3 0.2 -1')
    gui = child(world, 'gui', fullscreen='false')
    view = plugin(gui, 'MinimalScene', '3D View', engine='ogre2', scene='scene',
                  camera_pose='8 -12 11 0 0.55 1.2', background_color='0.55 0.75 0.92',
                  ambient_light='0.65 0.65 0.65')
    props = child(view, 'gz-gui')
    child(props, 'property', 'docked', key='state', type='string')
    for filename, name in [('GzSceneManager', 'Scene Manager'),
                           ('InteractiveViewControl', 'View Control'),
                           ('CameraTracking', 'Camera Tracking'),
                           ('WorldControl', 'World Control'), ('WorldStats', 'Statistics'),
                           ('Screenshot', 'Screenshot')]:
        element = plugin(gui, filename, name)
        if filename == 'CameraTracking':
            child(element, 'follow_target', 'trash_boat')
            child(element, 'follow_offset', '-5 -7 5')
    image_view = plugin(gui, 'ImageDisplay', 'Boat camera', topic='/vrx/camera')
    props = child(image_view, 'gz-gui')
    child(props, 'property', 'docked', key='state', type='string')
    for name, size, pose, color in [
        ('water', f'{config.canal_length} {2 * config.half_width} 0.05',
         f'{config.canal_length / 2} 0 -0.1 0 0 0', '0.04 0.27 0.38 1'),
        ('bank_port', f'{config.canal_length + 4} 2 1',
         f'{config.canal_length / 2} {config.half_width + 1} 0 0 0 0', '0.25 0.42 0.22 1'),
        ('bank_starboard', f'{config.canal_length + 4} 2 1',
         f'{config.canal_length / 2} {-config.half_width - 1} 0 0 0 0', '0.25 0.42 0.22 1'),
        ('bank_start', f'1 {2 * config.half_width} 1', '-0.5 0 0 0 0 0', '0.4 0.43 0.4 1'),
        ('bank_end', f'1 {2 * config.half_width} 1',
         f'{config.canal_length + 0.5} 0 0 0 0 0', '0.4 0.43 0.4 1'),
    ]:
        model = child(world, 'model', name=name)
        child(model, 'static', 'true')
        link = child(model, 'link', name='link')
        part(link, name, 'box', size, pose, color, collision=name != 'water')
    # Local, low-poly scenery stays outside the water and never supplies detections.
    for x in range(8, int(config.canal_length), 8):
        for side in [-1, 1]:
            model = child(world, 'model', name=f'tree_{x}_{side}')
            child(model, 'static', 'true')
            link = child(model, 'link', name='link')
            y = side * (config.half_width + 1)
            part(link, 'trunk', 'cylinder', '0.12 1.5', f'{x} {y} 1 0 0 0',
                 '0.22 0.16 0.1 1', False)
            part(link, 'leaves', 'sphere', '0.7', f'{x} {y} 2.1 0 0 0',
                 '0.12 0.35 0.15 1', False)
    make_boat(world, config)
    make_trash(world, config)
    plugin(world, 'libTrashWorld.so', 'trash_boat_vrx::TrashWorld', current=config.current,
           drift_gain=3.0, thruster_arm=0.65, thrust_limit=50.0, command_timeout=0.5,
           publish_rate=20.0, scoop_forward=1.5, scoop_lateral=1.0,
           canal_length=config.canal_length)
    ET.indent(root)
    return '<?xml version="1.0"?>\n' + ET.tostring(root, encoding='unicode') + '\n'


def main() -> None:
    """Write a validated generated world without starting the simulator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--current', type=float, default=0.05)
    parser.add_argument('--wave-amplitude', type=float, default=0.0)
    args = parser.parse_args()
    config = WorldConfig(seed=args.seed, current=args.current,
                         wave_amplitude=args.wave_amplitude)
    args.output.write_text(make_world(config))
