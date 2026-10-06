import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'arams_mission'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.yaml')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'config', 'maps'), glob('config/maps/*')),
        (os.path.join('share', package_name, 'models'), glob('models/*.pt')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Carlos Eduardo Alvarado Arriaga',
    maintainer_email='calvaradoarriaga@gmail.com',
    description='Mission nodes for the ARAMS hospital TurtleBot3 robotic nurse',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'tag_reader_node = arams_mission.tag_reader_node:main',
            'joy_speed_control_node = arams_mission.joy_speed_control_node:main',
            'room_navigator_node = arams_mission.room_navigator_node:main',
            'pinboard_approach_node = arams_mission.pinboard_approach_node:main',
            'patient_state_node = arams_mission.patient_state_node:main',
            'orchestrator_node = arams_mission.orchestrator_node:main',
            'collect_images = arams_mission.collect_images:main',
        ],
    },
)
