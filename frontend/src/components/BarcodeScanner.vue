<script lang="ts">
import { setZXingModuleOverrides } from 'vue-qrcode-reader'
import wasmUrl from 'zxing-wasm/reader/zxing_reader.wasm?url'

// 扫码用的 ZXing wasm 由本站自己提供，不从 jsDelivr CDN 加载。
// 放在普通 <script> 里：这个组件的代码块加载时执行一次，早于任何识别，且不进入主包。
setZXingModuleOverrides({
  locateFile: (path: string, prefix: string) => (path.endsWith('.wasm') ? wasmUrl : prefix + path),
})
</script>

<script setup lang="ts">
import { ref } from 'vue'
import { QrcodeStream } from 'vue-qrcode-reader'

type Formats = NonNullable<InstanceType<typeof QrcodeStream>['$props']['formats']>

defineProps<{ paused?: boolean }>()
const emit = defineEmits<{ detected: [text: string] }>()

const formats: Formats = ['qr_code', 'ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39']
const error = ref('')

function onDetect(codes: { rawValue: string }[]) {
  const text = codes[0]?.rawValue?.trim()
  if (text) emit('detected', text)
}

function onError(err: Error) {
  const messages: Record<string, string> = {
    NotAllowedError: '没有摄像头权限，请在浏览器设置里允许访问摄像头',
    NotFoundError: '没有找到摄像头',
    NotReadableError: '摄像头被其他应用占用',
    InsecureContextError: '需要通过 HTTPS 访问才能使用摄像头',
    StreamApiNotSupportedError: '当前浏览器不支持摄像头',
  }
  error.value = messages[err.name] ?? `无法打开摄像头：${err.message}`
}
</script>

<template>
  <div class="scanner">
    <qrcode-stream :formats="formats" :paused="paused" @detect="onDetect" @error="onError" />
  </div>
  <p class="hint center">{{ error || '把条码或二维码放进取景框' }}</p>
</template>

<style scoped>
.scanner {
  width: 100%;
  max-width: 480px;
  aspect-ratio: 1;
  margin: 0 auto;
  background: #000;
  overflow: hidden;
}
</style>
