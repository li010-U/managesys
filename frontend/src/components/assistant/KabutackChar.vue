<template>
  <svg
    class="kabutack-char"
    :class="charClass"
    viewBox="0 0 120 130"
    xmlns="http://www.w3.org/2000/svg"
    :style="charStyle"
    role="img"
    aria-labelledby="kab-title"
    aria-hidden="true"
  >
    <title id="kab-title">人工智能助手</title>
    <defs>
      <!-- 蓝色水滴星球渐变身体 -->
      <radialGradient id="kab-body-grad" cx="38%" cy="26%" r="82%">
        <stop offset="0%" stop-color="var(--c-hi)"/>
        <stop offset="35%" stop-color="var(--c-mid)"/>
        <stop offset="70%" stop-color="var(--c-main)"/>
        <stop offset="100%" stop-color="var(--c-deep)"/>
      </radialGradient>
      <!-- 眼白 -->
      <radialGradient id="kab-eye-grad" cx="42%" cy="32%" r="78%">
        <stop offset="0%" stop-color="#ffffff"/>
        <stop offset="70%" stop-color="#dbeafe"/>
        <stop offset="100%" stop-color="#bfdbfe"/>
      </radialGradient>
      <!-- 瞳孔 -->
      <radialGradient id="kab-pupil-grad" cx="42%" cy="36%" r="72%">
        <stop offset="0%" stop-color="#0ea5e9"/>
        <stop offset="100%" stop-color="#1e3a8a"/>
      </radialGradient>
      <!-- 中央经线光条 -->
      <linearGradient id="ring" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0"/>
        <stop offset="50%" stop-color="#ffffff" stop-opacity="0.55"/>
        <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
      </linearGradient>
      <!-- 柔和辉光：施加于粒子组，减少重复栅格化 -->
      <filter id="kab-glow" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="1.6" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <!-- 环境光晕：中心到边缘渐隐 -->
      <radialGradient id="kab-env-halo" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(140,200,255,0.16)"/>
        <stop offset="55%" stop-color="rgba(120,180,255,0.10)"/>
        <stop offset="100%" stop-color="rgba(120,180,255,0)"/>
      </radialGradient>
    </defs>

    <!-- 环境背景层：径向光晕垫底 + 极淡星光，突出球体与深度（装饰，忽略读屏） -->
    <g class="env-backdrop" aria-hidden="true">
      <circle class="env-halo" cx="60" cy="67" r="56" fill="none"/>
      <g class="env-stars">
        <circle class="env-star" cx="26" cy="34" r="1.1"/>
        <circle class="env-star" cx="104" cy="42" r="1.3"/>
        <circle class="env-star" cx="92" cy="100" r="0.9"/>
        <circle class="env-star" cx="20" cy="86" r="1.2"/>
        <circle class="env-star" cx="76" cy="24" r="1.0"/>
      </g>
    </g>

    <!-- 脚下柔光垫 / 睡眠云朵（装饰，忽略读屏） -->
    <g class="rest-aura" aria-hidden="true">
      <ellipse class="base-halo" cx="60" cy="121" rx="30" ry="4.5"/>
      <path class="nap-cloud" d="M52 124 C52 121 57 119 62 119 C67 119 72 121 72 124 C74 123 77 124 77 126 L43 126 C43 123.5 46 123 46 124.6 Z" fill="rgba(255,255,255,0.85)"/>
    </g>

    <!-- 星环主带（位于球体后方，环两侧从星球露出） -->
    <g class="orbit-plane" transform="rotate(-14 60 67)" aria-hidden="true">
      <!-- 宽大气环 -->
      <ellipse class="orbit atmosphere" cx="60" cy="67" rx="50" ry="20" fill="none"/>
      <!-- 主环 -->
      <ellipse class="orbit main" cx="60" cy="67" rx="49" ry="19" fill="none"/>
      <!-- 环缝（局部不连续，模拟土星环） -->
      <ellipse class="orbit split" cx="60" cy="67" rx="46.5" ry="18" fill="none"/>
    </g>

    <!-- 顶部光点（告警时变红并闪烁） -->
    <circle class="top-dot" :class="{ 'blink-danger': (dangerCount ?? 0) > 0 }" cx="60" cy="13" r="6.5" filter="url(#kab-glow)"/>

    <!-- 水滴星球身体 -->
    <path class="kab-body" d="M60 24 C85 24 100 43 100 67 C100 91 85 110 60 110 C35 110 20 91 20 67 C20 43 35 24 60 24 Z"/>
    <!-- 左上柔和高光（玻璃/星球质感） -->
    <ellipse class="body-shine" cx="43" cy="33" rx="18" ry="8" transform="rotate(-22 43 33)"/>
    <!-- 玻璃镜面高光：小而锐利的二次折射，增强立体发光 -->
    <ellipse class="specular" cx="49" cy="25.5" rx="6.5" ry="3.2" transform="rotate(-24 49 25.5)"/>
    <!-- 星球右下阴影，增强立体感 -->
    <ellipse class="planet-shade" cx="74" cy="82" rx="30" ry="22" transform="rotate(18 74 82)"/>
    <!-- 赤道浅色白斑，丰富球体肌理 -->
    <ellipse class="planet-blemish" cx="56" cy="78" rx="26" ry="6.5" transform="rotate(-8 56 78)"/>

    <!-- 中央经线光 -->
    <path class="meridian" d="M60 24 C60 52 60 82 60 110" fill="none"/>

    <!-- 环绕粒子：组上统一辉光，灵气随远近缩放 -->
    <g class="particle-orbit" transform="rotate(-14 60 67)" filter="url(#kab-glow)" aria-hidden="true">
      <circle class="particle particle-1" r="2.6">
        <animateMotion dur="9s" repeatCount="indefinite" path="M109 67 A49 19 0 1 1 11 67 A49 19 0 1 1 109 67"/>
      </circle>
      <circle class="particle particle-2" r="2">
        <animateMotion dur="14s" repeatCount="indefinite" begin="-4.5s" path="M109 67 A49 19 0 1 1 11 67 A49 19 0 1 1 109 67"/>
      </circle>
      <circle class="particle particle-3" r="3">
        <animateMotion dur="7s" repeatCount="indefinite" begin="-2.8s" path="M109 67 A49 19 0 1 1 11 67 A49 19 0 1 1 109 67"/>
      </circle>
    </g>
    <!-- 点缀星光（装饰，忽略读屏） -->
    <g class="star-sparkles" aria-hidden="true">
      <circle class="sparkle" cx="18" cy="52" r="1.6"/>
      <circle class="sparkle" cx="104" cy="60" r="1.4"/>
      <circle class="sparkle" cx="30" cy="97" r="1.3"/>
      <circle class="sparkle" cx="100" cy="88" r="1.7"/>
    </g>

    <!-- 脸部底色 -->
    <ellipse class="kab-face" cx="60" cy="67" rx="23" ry="21"/>

    <!-- 大眼睛 -->
    <g class="eye left-eye">
      <ellipse class="eyeball" cx="50" cy="62" rx="7.5" ry="9"/>
      <circle class="kab-pupil" cx="50" cy="63" r="3.4"/>
      <!-- 瞳孔多层高光：主眼神光 + 横向反光 -->
      <circle cx="48.2" cy="60.2" r="1.2" fill="#ffffff"/>
      <ellipse class="pupil-gloss left-gloss" cx="50.9" cy="64.4" rx="1.3" ry="0.5" transform="rotate(-14 50.9 64.4)"/>
      <!-- 睡眠睫毛 -->
      <path class="lash left-lash" d="M50 52 L50 55" fill="none"/>
      <!-- 软眼皮：随眨眼从上方滑落遮住眼球，更自然 -->
      <path class="eyelid left-eyelid" d="M42.5 62 A7.5 9 0 0 1 57.5 62 L57.5 58 A7.5 9 0 0 0 42.5 58 Z"/>
    </g>
    <g class="eye right-eye">
      <ellipse class="eyeball" cx="70" cy="62" rx="7.5" ry="9"/>
      <circle class="kab-pupil" cx="70" cy="63" r="3.4"/>
      <circle cx="68.2" cy="60.2" r="1.2" fill="#ffffff"/>
      <ellipse class="pupil-gloss right-gloss" cx="70.9" cy="64.4" rx="1.3" ry="0.5" transform="rotate(-14 70.9 64.4)"/>
      <path class="lash right-lash" d="M70 52 L70 55" fill="none"/>
      <!-- 软眼皮：随眨眼从上方滑落遮住眼球，更自然 -->
      <path class="eyelid right-eyelid" d="M62.5 62 A7.5 9 0 0 1 77.5 62 L77.5 58 A7.5 9 0 0 0 62.5 58 Z"/>
    </g>

    <!-- 眉毛 -->
    <path class="brow left-brow" d="M43 51 Q50 47 57 50" fill="none"/>
    <path class="brow right-brow" d="M63 50 Q70 47 77 51" fill="none"/>

    <!-- 脸颊 -->
    <ellipse class="cheek" cx="42" cy="71" rx="4.5" ry="3"/>
    <ellipse class="cheek" cx="78" cy="71" rx="4.5" ry="3"/>

    <!-- 嘴 -->
    <path class="mouth mouth-smile" d="M54 78 Q60 82 66 78" fill="none"/>
    <path class="mouth mouth-flat" d="M55 80 L65 80" fill="none"/>
    <path class="mouth mouth-open" d="M55 76 Q60 84 65 76 Q60 79.5 55 76 Z"/>
  </svg>
</template>

<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{
  mood?: string
  eyeX?: number
  eyeY?: number
  sleeping?: boolean
  squash?: boolean
  jumping?: boolean
  dangerCount?: number
  quiet?: boolean
}>()

const mood = computed(() => props.mood || "healthy")
const eyeX = computed(() => props.eyeX || 0)
const eyeY = computed(() => props.eyeY || 0)

const charClass = computed(() => ({
  sleeping: !!props.sleeping,
  squash: !!props.squash,
  jumping: !!props.jumping,
  quiet: !!props.quiet,
  ["mood-" + mood.value]: true,
}))

const charStyle = computed(() => ({
  "--eye-x": eyeX.value + "px",
  "--eye-y": eyeY.value + "px",
}))
</script>

<style scoped>
.kabutack-char {
  /* 统一美学变量：颜色与时长集中管理 */
  --c-hi: #eaf6ff;
  --c-mid: #7cc4ff;
  --c-main: #3f8cff;
  --c-deep: #1e40af;
  --pc-mid: #7cc4ff;
  --c-body-glow: rgba(63, 140, 255, 0.35);
  --pd1: 9s;
  --pd2: 14s;
  --pd3: 7s;

  display: block;
  overflow: visible;
  filter: drop-shadow(0 14px 24px var(--c-body-glow));
  animation: kab-breathe 3.6s ease-in-out infinite;
  transform-origin: center 82%;
  cursor: pointer;
}
.kabutack-char.squash { animation: kab-squash 0.26s ease-in-out; }
.kabutack-char.jumping { animation: kab-jump 0.9s ease-in-out infinite; }
/* 告警时整体轻微颤动（叠加在普通动画之上） */
.kabutack-char.mood-alert:not(.jumping):not(.squash) {
  animation: kab-breathe 3.6s ease-in-out infinite, kab-jitter 0.32s ease-in-out infinite;
}

/* 暗色模式变体：整体压暗、增强辉光 */
@media (prefers-color-scheme: dark) {
  .kabutack-char {
    --c-hi: #bfe0ff;
    --c-mid: #4f96ff;
    --c-main: #2763d8;
    --c-deep: #0f2a6b;
    --c-body-glow: rgba(63, 140, 255, 0.55);
  }
  .kabutack-char .body-shine { fill: rgba(255,255,255,0.20); }
  .kabutack-char .planet-shade { fill: rgba(8, 20, 60, 0.40); }
}

/* 尊重系统“减少动态效果”：静态呈现 */
@media (prefers-reduced-motion: reduce) {
  .kabutack-char,
  .kabutack-char.squash,
  .kabutack-char.jumping,
  .kabutack-char.mood-alert,
  .sparkle,
  .particle,
  .env-star,
  .eyelid,
  .top-dot,
  .orbit.main,
  .mouth-open,
  .mouth-smile { animation: none !important; }
  .kabutack-char .particle-orbit { animation-duration: 0s !important; }
  .eyelid { opacity: 0; }
}

/* 静默模式（桌面笼打开等场景）：暂停装饰动画以降低开销，静态呈现 */
.kabutack-char.quiet .env-star,
.kabutack-char.quiet .top-dot,
.kabutack-char.quiet .orbit.main,
.kabutack-char.quiet .mouth-open,
.kabutack-char.quiet .mouth-smile { animation: none !important; }
.kabutack-char.quiet .particle { animation: none !important; opacity: 0.5; }
.kabutack-char.quiet .particle-orbit,
.kabutack-char.quiet .star-sparkles { opacity: 0.35; }
.kabutack-char.quiet .sparkle { animation: none !important; opacity: 0.5; }

.kab-body { fill: url(#kab-body-grad); }
.body-shine { fill: rgba(255,255,255,0.32); }
/* 玻璃镜面高光：纯白小椭圆，制造折射亮点 */
.specular { fill: rgba(255,255,255,0.9); }
/* 环境背景：柔和光晕垫底，仅作氛围 */
.env-backdrop { pointer-events: none; }
.env-halo { fill: url(#kab-env-halo); }
.env-stars { opacity: 0.5; }
.env-star { fill: #e6f6ff; animation: kab-twinkle 3s ease-in-out infinite; }
.planet-shade { fill: rgba(15, 42, 115, 0.20); }
.planet-blemish { fill: rgba(255,255,255,0.10); }
.kab-face { fill: url(#kab-body-grad); }
.cheek { fill: rgba(94, 160, 255, 0.30); }
.base-halo { fill: rgba(125,196,255,0.30); }
.nap-cloud { opacity: 0.9; }
.meridian { stroke: url(#ring); stroke-width: 2; stroke-linecap: round; }

/* 星环分层：主环 + 大气环 + 环缝 */
.orbit { fill: none; stroke-linecap: round; }
.orbit.main {
  stroke: rgba(147,197,253,0.45);
  stroke-width: 1.6;
  stroke-dasharray: 2 6;
  animation: kab-flow 24s linear infinite;
}
.orbit.atmosphere { stroke: rgba(165,205,255,0.18); stroke-width: 4.6; }
.orbit.split { stroke: rgba(147,197,253,0.35); stroke-width: 1.1; stroke-dasharray: 34 26; }

/* 粒子沿轨道飞行并随深度缩放（纵深错觉） */
.particle { fill: #dff2ff; }
.particle-1 { opacity: 0.95; animation: kab-depth 9s linear infinite; }
.particle-2 { opacity: 0.8; animation: kab-depth 14s linear infinite; animation-delay: -4.5s; }
.particle-3 { opacity: 1; animation: kab-depth 7s linear infinite; animation-delay: -2.8s; }
.sparkle {
  fill: #e6f6ff;
  transform-box: fill-box;
  transform-origin: center;
  animation: kab-twinkle 2.4s ease-in-out infinite;
}
.sparkle:nth-child(2) { animation-delay: 0.8s; }
.sparkle:nth-child(3) { animation-delay: 1.5s; }
.sparkle:nth-child(4) { animation-delay: 0.4s; }
.top-dot {
  fill: url(#kab-body-grad);
  stroke: #bcdcff;
  stroke-width: 1.2;
  transform-box: fill-box;
  transform-origin: center;
  animation: kab-top-breathe 3s ease-in-out infinite;
}
.top-dot.blink-danger {
  fill: #ff5d6c;
  stroke: #ff8f99;
  animation: kab-blink-warning 0.8s ease-in-out infinite;
}
.kabutack-char.sleeping .top-dot { animation: none; opacity: 0.6; }
.eye {
  transform-box: fill-box;
  transform-origin: center;
}
/* 软眼皮：整体不再压扁眼睛，由眼皮滑落实现自然眨眼 */
.eyelid {
  fill: url(#kab-body-grad);
  transform-box: fill-box;
  transform-origin: center top;
  animation: kab-lid 4.6s ease-in-out infinite;
}
.kabutack-char.sleeping .eye { opacity: 0; transition: opacity 0.5s ease; }
.kabutack-char.sleeping .eyelid { animation: none; }
.eyeball { fill: url(#kab-eye-grad); stroke: #bfdbfe; stroke-width: 1; }
.kab-pupil {
  fill: url(#kab-pupil-grad);
  transform: translate(var(--eye-x, 0px), var(--eye-y, 0px));
  transition: transform 0.14s ease-out;
}
/* 瞳孔多层高光：仅健康态可见，避让视线追踪 */
.pupil-gloss {
  fill: rgba(255,255,255,0.85);
  transition: opacity 0.14s ease;
}
.kabutack-char.mood-alert .pupil-gloss,
.kabutack-char.mood-attention .pupil-gloss { opacity: 0.35; }
/* 睡眠睫毛：默认隐藏，睡眠时显示 */
.lash {
  stroke: #1e3a8a;
  stroke-width: 1.6;
  stroke-linecap: round;
  opacity: 0;
  transition: opacity 0.4s ease;
}
.brow {
  stroke: #1e3a8a;
  stroke-width: 2.6;
  stroke-linecap: round;
  transform-box: fill-box;
  transform-origin: center;
  transition: transform 0.25s ease;
}

/* 情绪：注意 */
.kabutack-char.mood-attention .eyeball { fill: #fff8dd; stroke: #fde68a; }
.kabutack-char.mood-attention .top-dot { fill: #ffd166; stroke: #ffe08a; }

/* 情绪：告警（眉毛上挑成 V 形 + 全身微颤已在根级） */
.kabutack-char.mood-alert .kab-body { filter: brightness(1.06) saturate(1.2); }
.kabutack-char.mood-alert .eyeball { fill: #ffe3dd; stroke: #ffb0a3; }
.kabutack-char.mood-alert .kab-pupil { fill: #f87171; }
.kabutack-char.mood-alert .cheek { fill: rgba(255, 84, 108, 0.55); }
.kabutack-char.mood-alert .top-dot { fill: #ff5d6c; stroke: #ff8f99; }

/* 表情：健康（微笑） */
.kabutack-char.mood-healthy .left-brow { transform: rotate(14deg) translateY(-1px); }
.kabutack-char.mood-healthy .right-brow { transform: rotate(-14deg) translateY(-1px); }
.kabutack-char.mood-healthy .mouth-smile { display: block; }

/* 表情：注意（平静） */
.kabutack-char.mood-attention .left-brow { transform: rotate(-9deg); }
.kabutack-char.mood-attention .right-brow { transform: rotate(9deg); }
.kabutack-char.mood-attention .mouth-flat { display: block; }
.kabutack-char.mood-attention .mouth-smile,
.kabutack-char.mood-attention .mouth-open { display: none; }

/* 表情：告警（张嘴 + 竖眉） */
.kabutack-char.mood-alert .left-brow { transform: rotate(-22deg) translateY(1px); }
.kabutack-char.mood-alert .right-brow { transform: rotate(22deg) translateY(1px); }
.kabutack-char.mood-alert .mouth-open { display: block; }
.kabutack-char.mood-alert .mouth-smile,
.kabutack-char.mood-alert .mouth-flat { display: none; }

.mouth-smile, .mouth-flat, .mouth-open { display: none; }
.mouth-smile { stroke: #1e40af; stroke-width: 2.6; stroke-linecap: round; }
.mouth-flat { stroke: #1e40af; stroke-width: 2.6; stroke-linecap: round; }
.mouth-open { fill: #1e40af; stroke: #1e40af; stroke-width: 1.4; stroke-linecap: round; }
/* 嘴部动态：告警张嘴张合 + 微笑收放 */
.kabutack-char.mood-alert .mouth-open {
  transform-box: fill-box;
  transform-origin: center;
  animation: kab-mouth-alert 0.9s ease-in-out infinite;
}
.kabutack-char.mood-healthy .mouth-smile {
  transform-box: fill-box;
  transform-origin: center;
  animation: kab-mouth-smile 3.2s ease-in-out infinite;
}

/* 睡眠 */
.kabutack-char.sleeping .eye { opacity: 0; transition: opacity 0.5s ease; }
.kabutack-char.sleeping .lash { opacity: 1; }
.kabutack-char.sleeping .mouth-smile, .kabutack-char.sleeping .mouth-flat { display: block; }
.kabutack-char.sleeping .mouth-open { display: none; }
.kabutack-char.sleeping .left-brow { transform: rotate(9deg) translateY(2px); }
.kabutack-char.sleeping .right-brow { transform: rotate(-9deg) translateY(2px); }
.kabutack-char.sleeping .rest-aura { opacity: 1; }
.kabutack-char.sleeping .nap-cloud { opacity: 0.55; transform: translateY(1px); }
.kabutack-char.sleeping .orbit { opacity: 0.4; }
.kabutack-char.sleeping .particle { opacity: 0.4; }
.kabutack-char.sleeping .particle-orbit { opacity: 0.4; }
.kabutack-char.sleeping .star-sparkles { opacity: 0.3; }
.kabutack-char.sleeping .meridian { opacity: 0.35; }
.kabutack-char.sleeping .base-halo { opacity: 0.4; }
.kabutack-char.sleeping .env-backdrop { opacity: 0.5; }
.kabutack-char.sleeping .specular { opacity: 0.5; }
.kabutack-char.sleeping .mouth-smile,
.kabutack-char.sleeping .mouth-open { animation: none !important; }

@keyframes kab-blink-warning {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
@keyframes kab-blink {
  0%, 93%, 100% { transform: scaleY(1); opacity: 1; }
  95% { transform: scaleY(0.12); opacity: 0.9; }
  97% { transform: scaleY(1); }
}
@keyframes kab-breathe {
  0%, 100% { transform: translateY(0) scaleY(1); }
  50% { transform: translateY(-3px) scaleY(1.02); }
}
@keyframes kab-jump {
  0%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px) rotate(-2deg); }
  55% { transform: translateY(-2px) scaleY(0.96); }
  75% { transform: translateY(-5px); }
}
@keyframes kab-squash {
  0% { transform: scale(1.25, 0.75); }
  50% { transform: scale(0.92, 1.12); }
  100% { transform: scale(1, 1); }
}
@keyframes kab-twinkle {
  0%, 100% { opacity: 0.25; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.35); }
}
/* 告警轻微颤动 */
@keyframes kab-jitter {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-0.8px) translateY(0.5px); }
  50% { transform: translateX(0.6px) translateY(-0.4px); }
  75% { transform: translateX(-0.4px) translateY(0.3px); }
}
/* 粒子沿轨道远近的缩放/透明度纵深 */
@keyframes kab-depth {
  0%, 100% { transform: scale(0.55); opacity: 0.45; }
  18% { transform: scale(1); opacity: 1; }
  50% { transform: scale(0.6); opacity: 0.5; }
  68% { transform: scale(1.05); opacity: 1; }
}
/* 软眼皮滑落闭合（眨眼） */
@keyframes kab-lid {
  0%, 92%, 100% { transform: translateY(-9px); opacity: 0; }
  95% { transform: translateY(1px); opacity: 1; }
  97% { transform: translateY(-9px); opacity: 0; }
}
/* 星环缓慢自转流光 */
@keyframes kab-flow {
  from { stroke-dashoffset: 0; }
  to { stroke-dashoffset: 96; }
}
/* 顶部呼吸灯（待机） */
@keyframes kab-top-breathe {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.12); }
}
/* 告警张嘴张合 */
@keyframes kab-mouth-alert {
  0%, 100% { transform: scaleY(1); }
  45% { transform: scaleY(1.25); }
  60% { transform: scaleY(1); }
}
/* 微笑收放（微表情） */
@keyframes kab-mouth-smile {
  0%, 100% { transform: scaleY(1); }
  50% { transform: scaleY(1.15); }
}
</style>













