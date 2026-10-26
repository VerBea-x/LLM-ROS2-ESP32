cmake_minimum_required(VERSION 3.8)
project(nav_g03)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/NavigateTo.srv"
)

install(PROGRAMS
  nodes/navigate_to_server.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME navigate_to_server
)
install(PROGRAMS
  nodes/publish_initial_pose.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME publish_initial_pose
)
install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})

ament_export_dependencies(rosidl_default_runtime)
ament_package()
