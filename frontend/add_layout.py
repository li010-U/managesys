import os
os.chdir('D:/managesys/frontend')

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add FullScreen import
old_import = 'Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard'
new_import = 'Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard, FullScreen'
content = content.replace(old_import, new_import)

# 2. Add isFullscreen and toggleFullscreen (minimal)
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

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Layout changes applied (without CSS)')
