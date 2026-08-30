# deploy.sh 部署问题排查

## 1. deploy.sh 超时（路径轮换时）

**现象**：`bash /opt/ttdazi/rotate_admin_path.sh` 在 `deploy.sh` 阶段超时退出。

**根因**：rotate_admin_path.sh 内部调用了 `bash /opt/ttdazi/deploy.sh`，其中包含 `npm run build`（约10s）+ rsync 到 Server B。当终端超时设置 < 60s 时会被切断。

**排查方式**：
```bash
# 检查本地 dist 是否已构建成功
ls -la /opt/ttdazi/frontend/dist/index.html

# 检查 Server B 是否已同步
ssh ubuntu@82.157.202.24 "ls -la /home/ubuntu/ttdazi-frontend/index.html"
```

**手动完成部署**：
```bash
cd /opt/ttdazi/frontend && npm run build && bash /opt/ttdazi/deploy.sh
```

## 2. 旧文件残留导致浏览器加载旧版本

**现象**：修改已部署，浏览器 Ctrl+F5 仍显示旧版本。

**根因**：Vite 构建产生新 hash 文件，但旧 hash 文件在 Server B 上堆积。deploy.sh 的 rsync 不带 `--delete` 时不会清理旧文件。

**排查**：
```bash
ssh ubuntu@82.157.202.24 "ls /home/ubuntu/ttdazi-frontend/assets/index-*.js | wc -l"
# 如果 > 1，有旧文件残留
```

**修复**：手动 rsync 带 --delete：
```bash
cd /opt/ttdazi/frontend && rsync -avz --delete dist/ ubuntu@82.157.202.24:/home/ubuntu/ttdazi-frontend/
```

## 3. 构建产物与源码不一致

**现象**：源文件已修改但部署后效果不符合预期。

**排查**：
```bash
# 检查编译产物中的关键字符串
grep -o '期望的关键词' /opt/ttdazi/frontend/dist/assets/index-*.js

# 对比 Server B 上的文件
ssh ubuntu@82.157.202.24 "grep -o '期望的关键词' /home/ubuntu/ttdazi-frontend/assets/index-*.js"
```

**修复**：重新构建 + 带 --delete 的 rsync。

## 4. deploy.sh 误报成功

**现象**：deploy.sh 输出 `✅ 前端编译完成` 但构建实际失败。

**根因**：deploy.sh 只检查 `npm run build` 的 exit code。某些错误（如 CSS 语法警告）exit code 仍为 0。

**准确检查方法**：
```bash
npm run build 2>&1 | tail -5
# 确认最后一行是 "✓ built in Xs"
```
