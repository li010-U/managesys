import os
os.chdir('D:/managesys/frontend')

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add FullScreen import
old_import = 'Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard'
new_import = 'Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard, FullScreen'
content = content.replace(old_import, new_import)

# 2. Add isFullscreen and toggleFullscreen
old_vars = 'const chatVisible = ref(false)'
new_vars = '''const chatVisible = ref(false)
const isFullscreen = ref(false)

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}'''
content = content.replace(old_vars, new_vars)

# 3. Add fullscreen button
old_header = '<div class="user-info">'
new_header = '''<el-tooltip content="全屏" placement="bottom">
            <el-button text class="header-btn" @click="toggleFullscreen">
              <el-icon size="20">
                <FullScreen v-if="!isFullscreen" />
                <Close v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
          <div class="user-info">'''
content = content.replace(old_header, new_header)

# 4. Add fixed styles - insert before </style>
style_addition = '''

/* 全屏按钮 */
.fullscreen-btn {
  margin: 0 4px;
}

/* 主容器布局修复 */
:deep(.el-container) {
  height: 100%;
  overflow: hidden;
}

.main-container {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

.app-main {
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--app-bg-page);
  flex: 1;
  min-height: 0;
  height: 100%;
}
'''

content = content.replace('</style>', style_addition + '\n</style>')

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('All changes applied!')
