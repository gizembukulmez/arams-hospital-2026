"""Hospital supervisor controller.

Zwei Aufgaben:

1. Patientenzustaende zufaellig erzeugen: Bei jedem Durchlauf wird der
   physische Zustand jedes Patienten zufaellig gesetzt: im Bett liegend,
   auf dem Boden liegend (kollabiert) oder stehend.
   Setze ARAMS_PATIENT_SEED, um einen Durchlauf reproduzierbar zu machen.

2. Tuersteuerung: Stellt ROS-Services bereit (open_door_1, open_door_2,
   open_door_3), damit der Roboter die Tueren zu den Patientenzimmern
   oeffnen kann. Optional ueber ARAMS_DOOR_OPEN_ANGLE konfigurierbar.
"""

import os
import random

from controller import Supervisor

try:
    import rclpy
    from rclpy.node import Node
    from std_srvs.srv import Trigger
    ROS_AVAILABLE = True
except ImportError:  # rclpy nicht verfuegbar -> nur Patienten-Logik
    ROS_AVAILABLE = False


# --- Patienten -------------------------------------------------------------

# Patient-DEF-Name -> (x, y) des zugehoerigen Bettes.
# Alle Betten haben dieselbe Ausrichtung (rotation 0 0 1 1.5708),
# daher koennen die Posen relativ zur Bettposition berechnet werden.
PATIENT_BEDS = {
    'PATIENT_1': (-6.5, 6.0),
    'PATIENT_2': (0.0, 6.5),
    'PATIENT_3': (6.5, 6.0),
}

# Standhoehe des Pedestrian-Modells (siehe pedestrian.py ROOT_HEIGHT).
STANDING_HEIGHT = 1.27

STATES = ('in_bed', 'on_floor', 'standing')


def pose_for(state, bed_x, bed_y):
    """Liefert (translation, rotation) fuer einen Patientenzustand."""
    if state == 'in_bed':
        # Auf der Matratze liegend (entspricht der urspruenglich platzierten Pose).
        return [bed_x - 0.41, bed_y, 0.8], [0.0, 1.0, 0.0, -1.5708]
    if state == 'on_floor':
        # Kollabiert auf dem Boden, direkt vor dem Bett (Richtung Rauminneres).
        return [bed_x, bed_y - 1.0, 0.15], [-0.4377, 0.8629, -0.2527, -1.7178]
    # standing: aufrecht, einen Schritt vor dem Bett.
    return [bed_x, bed_y - 1.3, STANDING_HEIGHT], [0.0, 0.0, 1.0, 0.0]


# --- Pinnwand (ArUco-Tag neben dem TurtleBot) ------------------------------

# DEF-Name der ImageTexture auf der Pinnwand neben dem TurtleBot.
PINNWAND_TEX_DEF = 'PINNWAND_TEX'
ARUCO_IDS = (1, 2, 3)


def randomize_pinnwand(robot, rng):
    """Zeigt zu Beginn der Simulation einen zufaelligen ArUco-Tag
    (ID 1, 2 oder 3) auf der Pinnwand neben dem TurtleBot an."""
    texture = robot.getFromDef(PINNWAND_TEX_DEF)
    if texture is None:
        print('[hospital_supervisor] WARNUNG: Pinnwand-Textur {} nicht gefunden'
              .format(PINNWAND_TEX_DEF))
        return
    tag_id = rng.choice(ARUCO_IDS)
    # Absoluter Pfad: zur Laufzeit gesetzte url-Felder werden relativ zum
    # Arbeitsverzeichnis des Controllers aufgeloest, nicht zum Weltfile.
    # controllers/hospital_supervisor/ -> Paketwurzel -> worlds/textures/apriltag/
    pkg_share = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    url = os.path.join(pkg_share, 'worlds', 'textures', 'apriltag',
                       'tag41_12_{:05d}.png'.format(tag_id))
    texture.getField('url').setMFString(0, url)
    print('[hospital_supervisor] Pinnwand zeigt AprilTag 41h12 ID {}'.format(tag_id))


def randomize_patients(robot, rng):
    print('[hospital_supervisor] Patientenzustaende fuer diesen Durchlauf:')
    for def_name, (bed_x, bed_y) in PATIENT_BEDS.items():
        node = robot.getFromDef(def_name)
        if node is None:
            print('[hospital_supervisor] WARNUNG: Knoten {} nicht gefunden'.format(def_name))
            continue
        state = rng.choice(STATES)
        translation, rotation = pose_for(state, bed_x, bed_y)
        node.getField('translation').setSFVec3f(translation)
        node.getField('rotation').setSFRotation(rotation)
        node.resetPhysics()
        print('  {}: {}'.format(def_name, state))


# --- Tueren ----------------------------------------------------------------

# Tuer-Nummer -> DEF-Name der Tuer im Weltfile.
DOORS = {
    1: 'DOOR_1',
    2: 'DOOR_2',
    3: 'DOOR_3',
}

# Hinge-Winkel der geoeffneten bzw. geschlossenen Tuer.
OPEN_ANGLE = float(os.environ.get('ARAMS_DOOR_OPEN_ANGLE', '1.5708'))
CLOSED_ANGLE = float(os.environ.get('ARAMS_DOOR_CLOSED_ANGLE', '0.0'))


def set_door(robot, def_name, open_door_flag):
    """Oeffnet oder schliesst die angegebene Tuer ueber das position-Feld
    des Hinge-Joints.

    Liefert (success, message).
    """
    node = robot.getFromDef(def_name)
    if node is None:
        return False, 'Tuer {} nicht gefunden'.format(def_name)
    position_field = node.getField('position')
    if position_field is None:
        return False, 'Tuer {} hat kein position-Feld'.format(def_name)
    position_field.setSFFloat(OPEN_ANGLE if open_door_flag else CLOSED_ANGLE)
    node.resetPhysics()
    verb = 'geoeffnet' if open_door_flag else 'geschlossen'
    return True, 'Tuer {} {}'.format(def_name, verb)


class HospitalSupervisorNode(Node):
    """ROS-Node mit den open_door_N-Services."""

    def __init__(self, robot):
        super().__init__('hospital_supervisor')
        self._robot = robot
        self._services = []
        for door_id, def_name in DOORS.items():
            for action, open_flag in (('open', True), ('close', False)):
                service_name = '{}_door_{}'.format(action, door_id)
                # Default-Argumente binden Tuer und Aktion fest an den Service.
                self._services.append(self.create_service(
                    Trigger, service_name,
                    lambda req, resp, dn=def_name, of=open_flag, sn=service_name:
                        self._handle(req, resp, dn, of, sn)))
                self.get_logger().info('Service /{} bereit ({})'.format(service_name, def_name))

    def _handle(self, request, response, def_name, open_flag, service_name):
        success, message = set_door(self._robot, def_name, open_flag)
        response.success = success
        response.message = message
        log = self.get_logger().info if success else self.get_logger().warn
        log('/{}: {}'.format(service_name, message))
        return response


# --- Hauptprogramm ---------------------------------------------------------

def main():
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())

    seed = os.environ.get('ARAMS_PATIENT_SEED')
    rng = random.Random(int(seed)) if seed is not None else random.Random()
    if seed is not None:
        print('[hospital_supervisor] Verwende festen Seed: {}'.format(seed))

    randomize_patients(robot, rng)
    randomize_pinnwand(robot, rng)

    node = None
    if ROS_AVAILABLE:
        rclpy.init()
        node = HospitalSupervisorNode(robot)
    else:
        print('[hospital_supervisor] WARNUNG: rclpy nicht verfuegbar, '
              'Tuer-Services deaktiviert.')

    try:
        while robot.step(timestep) != -1:
            if node is not None:
                rclpy.spin_once(node, timeout_sec=0)
    finally:
        if node is not None:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
