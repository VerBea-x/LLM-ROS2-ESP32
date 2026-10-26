"""Truth-localized integration fixture: slip=0 required; never localization evidence."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration,PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params=LaunchConfiguration('params_file');map_file=LaunchConfiguration('map')
    return LaunchDescription([
        DeclareLaunchArgument('params_file'),DeclareLaunchArgument('map'),
        Node(package='tf2_ros',executable='static_transform_publisher',name='truth_fixture_map_odom',
             arguments=['--x','0','--y','0','--z','0','--yaw','0','--pitch','0','--roll','0','--frame-id','map','--child-frame-id','odom']),
        Node(package='nav2_map_server',executable='map_server',name='map_server',
             parameters=[{'yaml_filename':map_file,'use_sim_time':False}]),
        Node(package='nav2_lifecycle_manager',executable='lifecycle_manager',name='truth_fixture_map_lifecycle',
             parameters=[{'autostart':True,'node_names':['map_server'],'use_sim_time':False}]),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(PathJoinSubstitution([
             FindPackageShare('nav2_bringup'),'launch','navigation_launch.py'])),
             launch_arguments={'params_file':params,'use_sim_time':'false','autostart':'true'}.items()),
        Node(package='nav_g03',executable='navigate_to_server',arguments=['--timeout','60'],output='screen'),
    ])
