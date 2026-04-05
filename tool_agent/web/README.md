# VideoBuddy Web

视频理解智能体的 Web 前端界面。

## 技术栈

- Vue 3 + Composition API + TypeScript
- Vite
- Naive UI（暗黑主题）
- Pinia 状态管理
- marked + highlight.js (Markdown 渲染)

## 安装与运行

```bash
cd tool_agent/web

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

## 功能

- 视频上传（拖拽或点击选择）
- 视频链接导入
- 视频分析（抽帧 + Caption + ASR）
- ChatGPT 风格对话界面
- Markdown 消息渲染
- 对话历史管理
- 纯文本问答模式（无需上传视频）

## 配置

前端默认连接 `http://localhost:18080` 的后端 API。

如需修改后端地址，编辑 `vite.config.ts` 中的 proxy 配置。

## 目录结构

```
web/
├── src/
│   ├── App.vue           # 主组件
│   ├── main.ts          # 入口
│   ├── stores/
│   │   └── session.ts   # 会话状态管理
│   └── api/
│       └── client.ts    # API 客户端
├── public/
│   └── videobuddy.png  # Logo
├── index.html
├── vite.config.ts
└── package.json
```
