# 页面水平滚动修复（overflow-x: hidden）

## 症状

「我的」页面或其他页面可以左右滑动，出现布局错乱（元素偏移、白边、内容水平溢出）。

## 根因

`.page-container` 类在 `global.css` 中定义了 `max-width: 100vw` 但缺少 `overflow-x: hidden`。当页面内部某个子元素宽度超出 100vw（如绝对定位元素、过宽的3D变换元素、使用了 `translateX` 的动画元素）时，页面可以横向滚动。

## 修复

```css
/* frontend/src/assets/global.css */
.page-container {
  min-height: 100vh;
  max-width: 100vw;
  overflow-x: hidden;  /* ← 添加这行 */
  padding-bottom: 64px;
}
```

## 排查

1. 在浏览器开发者工具中检查 `.page-container` 的计算样式
2. 查找是否有子元素超出容器宽度：
   ```js
   // 在控制台执行
   document.querySelectorAll('*').forEach(el => {
     const rect = el.getBoundingClientRect();
     if (rect.right > window.innerWidth) console.log(el, rect.right - window.innerWidth);
   });
   ```
3. 常见的超宽原因：
   - `transform: rotateX()` 3D 卡片倾斜后宽度增加
   - `position: absolute` 元素定位在容器外部
   - `white-space: nowrap` 长文本不换行
   - 过宽的 `box-shadow`（但 shadow 不触发滚动）

## 注意

`overflow-x: hidden` 会裁剪 `position: absolute` 超出容器的子元素。如果页面有需要溢出的元素（如下拉菜单、弹窗），需要确保这些元素的父级不设置 `overflow: hidden`。

## 影响范围

本修复影响所有使用 `.page-container` 的页面（Profile.vue、List.vue、PlaymateLogin.vue 等），全局生效。
