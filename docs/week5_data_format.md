# 第5周数据交接

先写独立真值，再运行检测器。同一组20场景分别以0.3、0.5、0.7回放；NMS设置保持一致。
原课件要求教师公共10张与自采10张。用户已选择改用20张公开室内场景，当前冻结于 `data/coco_indoor20_v2/dataset.json`，共享标注在 `data/annotations/instances_val2017.json`。这是经授权的替代实验，原硬件/自采项不自动通过；不再要求无摄像头小车采图。

标注JSON的scenes列表每项填写：sample_id、source_group（public/custom）、image（相对路径）、image_sha256、truth_source、truth_frozen_at、objects。
objects每项为 `{"label":"cup","bbox":[10,20,70,90]}`，原图像素坐标。
预测JSON为 `{"scenes":{"场景编号":[{"label":"cup","bbox":[10,20,70,90],"score":0.8}]}}`。

执行 `PYTHONPATH=src python3 -m course_audit.detection_metrics --dataset 数据集.json --predictions 预测.json --output evidence/reports/week5_detection.json`。
输出保存每个场景×阈值的TP/FP/FN及匹配IoU，分类错报同时产生FP与FN，多余重复框产生FP。

旧vision_metrics.py只适合单目标存在性演示；课程验收使用detection_metrics.py。未取得图像和独立标注时不生成课程成绩。
相机标定文件、棋盘格实测尺寸、检测节点与30秒性能记录仍为另行验收项；离线统计不能替代。

当前真实推理与逐图可视化：`python3 scripts/run_public_detection.py --run-tag 新名字`，然后 `python3 scripts/render_public_detection.py --run-tag 同一个新名字`。默认使用室内V2，已有结果拒绝覆盖；原始COCO框格式转为本项目xyxy后评分，不能直接混用xywh。图片没有地图坐标，不用于声称真实视觉定位。
