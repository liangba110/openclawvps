#!/bin/bash
# ═══════════════════════════════════════════
#  Skills GitHub 同步脚本
#  用法: bash /opt/ttdazi/ops/sync_skills.sh [commit_message]
# ═══════════════════════════════════════════
set -e

REPO_DIR="/tmp/ops-bundle-repo"
SKILLS_DIR="$HOME/.hermes/skills"
MSG="${1:-📦 skills同步 $(date +%Y-%m-%d\ %H:%M)}"

echo "🔄 Skills GitHub 同步"
echo "═══════════════════════════"

# 1. 确保repo存在
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "📦 克隆仓库..."
    git clone git@github.com:liangba110/ops-bundle.git "$REPO_DIR" 2>/dev/null || {
        echo "⚠️ 克隆失败，尝试创建..."
        mkdir -p "$REPO_DIR"
        cd "$REPO_DIR"
        git init
        git remote add origin git@github.com:liangba110/ops-bundle.git
        git fetch origin main 2>/dev/null || true
        git checkout main 2>/dev/null || git checkout -b main
    }
fi

cd "$REPO_DIR"

# 2. 同步skills目录
echo ""
echo "📁 同步skills..."
mkdir -p skills

# 按category分组复制
find "$SKILLS_DIR" -name "SKILL.md" -type f 2>/dev/null | while read skill_file; do
    skill_dir=$(dirname "$skill_file")
    skill_name=$(basename "$skill_dir")
    category=$(basename "$(dirname "$skill_dir")")
    
    target_dir="skills/$category/$skill_name"
    mkdir -p "$target_dir"
    
    # 复制SKILL.md
    cp "$skill_file" "$target_dir/"
    
    # 复制linked files（references, templates, scripts, assets）
    for sub in references templates scripts assets; do
        if [ -d "$skill_dir/$sub" ]; then
            cp -r "$skill_dir/$sub" "$target_dir/"
        fi
    done
done

# 3. 统计
skill_count=$(find skills -name "SKILL.md" | wc -l)
total_size=$(du -sh skills | awk '{print $1}')
echo "  ✅ 同步了 $skill_count 个skills ($total_size)"

# 4. Git操作
echo ""
echo "📝 Git提交..."
git add -A
if git diff --cached --quiet; then
    echo "  ℹ️ 无变更，跳过提交"
else
    git commit -m "$MSG"
    echo "  ✅ 已提交"
    
    echo ""
    echo "🚀 推送..."
    git push origin main 2>&1
    echo "  ✅ 已推送到 GitHub"
fi

echo ""
echo "═══════════════════════════"
echo "✅ 同步完成"
echo "🔗 https://github.com/liangba110/ops-bundle/tree/main/skills"
