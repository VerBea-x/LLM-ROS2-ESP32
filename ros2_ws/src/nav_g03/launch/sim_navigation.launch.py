from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    map_yaml = LaunchConfiguration("map")
    params = LaunchConfiguration("params_file")
    timeout = LaunchConfiguration("navigate_timeout_s")
    nav2_share = FindPackageShare("nav2_bringup")
    default_params = PathJoinSubstitution([FindPackageShare("nav_g03"), "config", "nav2_params.yaml"])
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([nav2_share, "launch", "localization_launch.py"])),
        launch_arguments={"map": map_yaml, "params_file": params,
                          "autostart": "true", "use_sim_time": "false"}.items())
    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([nav2_share, "launch", "navigation_launch.py"])),
        launch_arguments={"params_file": params,
                          "autostart": "true", "use_sim_time": "false"}.items())
    navigate_service = Node(package="nav_g03", executable="navigate_to_server",
                            name="course_navigate_to_server", output="screen",
                            arguments=["--timeout", timeout])
    return LaunchDescription([
        DeclareLaunchArgument("map", description="Path to fixed-world map YAML"),
        DeclareLaunchArgument("params_file", default_value=default_params),
        DeclareLaunchArgument("navigate_timeout_s", default_value="60"),
        localization, navigation, navigate_service,
    ])
