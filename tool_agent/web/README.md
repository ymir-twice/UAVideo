# VideoBuddy Web 前端

VideoBuddy 视频理解智能体的 Web 界面。

## 技术栈

- Vue 3 + Composition API + TypeScript
- Vite
- Naive UI（暗黑主题，暖色调）
- Pinia 状态管理
- marked + highlight.js（Markdown 渲染）

## 安装与运行

```bash
cd tool_agent/web

# 安装依赖
npm install

# 开发模式（需先启动后端）
npm run dev
```

## 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录，可部署到任意静态服务器。

## 访问地址

| 环境 | 地址 |
|------|------|
| 本地开发 | http://localhost:8801 |
| 公网访问 | http://js3.blockelite.cn:15577 |

## 功能

- 视频上传（拖拽或点击选择）
- 视频链接导入
- 视频分析（抽帧 + Caption + ASR）
- ChatGPT 风格对话界面
- Markdown 消息渲染
- 对话历史管理
- 纯文本问答模式（无需上传视频）

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
│   └── videobuddy.png   # Logo
├── index.html
├── vite.config.ts
└── package.json
```

## API 配置

前端默认连接 `http://localhost:8800` 的后端 API。

修改 `vite.config.ts` 中的 proxy 配置可更改后端地址。
