import re

with open('src/layouts/MainLayout.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports
if 'FullScreen' not in content:
    old_import = 'Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard'
    new_import = 'Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard, FullScreen'
    content = content.replace(old_import, new_import)

# 2. Add isFullscreen variable
if 'const isFullscreen = ref' not in content:
    content = content.replace(
        'const chatVisible = ref(false)',
        'const chatVisible = ref(false)\nconst isFullscreen = ref(false)'
    )

# 3. Add toggleFullscreen function
if 'function toggleFullscreen()' not in content:
    old_func = '''function handleCommand(cmd: string) {
    if (cmd === "logout") { 
      authStore.logout(); 
      router.push("/login") 
    }
    else if (cmd === "profile") router.push("/profile")
  }'''
    new_func = '''function handleCommand(cmd: string) {
    if (cmd === "logout") { 
      authStore.logout(); 
      router.push("/login") 
    }
    else if (cmd === "profile") router.push("/profile")
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen()
      isFullscreen.value = true
    } else {
      document.exitFullscreen()
      isFullscreen.value = false
    }
  }'''
    content = content.replace(old_func, new_func)

# 4. Add fullscreen button
if 'el-tooltip content="全屏"' not in content:
    old_button = '<div class="user-info">'
    new_button = '''<el-tooltip content="全屏" placement="bottom">
            <el-button text class="header-btn" @click="toggleFullscreen">
              <el-icon size="20">
                <FullScreen v-if="!isFullscreen" />
                <Close v-else />
              </el-icon>
            </el-button>
          </el-tooltip>
          <div class="user-info">'''
    content = content.replace(old_button, new_button)

with open('src/layouts/MainLayout.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done!')
