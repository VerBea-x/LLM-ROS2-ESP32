#!/usr/bin/env python3
"""Read-only graph probe; never publishes velocity or actuates hardware."""
import argparse
import json
import time
from pathlib import Path
import rclpy
from rclpy.node import Node

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=float,default=8);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();rclpy.init();n=Node('course_esp32_readonly_probe');start=time.monotonic()
    while time.monotonic()-start<a.seconds:rclpy.spin_once(n,timeout_sec=.2)
    topics=n.get_topic_names_and_types()
    report={'source_kind':'read_only_ros_graph_snapshot','no_actuation':True,
      'topics':[{'name':name,'types':types,'publishers':n.count_publishers(name)} for name,types in topics],
      'nodes':n.get_node_names(),'limitations':['Topic presence alone does not verify hardware, firmware, freshness, or physical movement.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2));n.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
