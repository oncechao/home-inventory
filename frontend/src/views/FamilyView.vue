<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { api } from '../api'
import { clearSession, currentFamily, refreshFamilies, session, setCurrentFamily } from '../session'
import type { FamilyDetail, Invite } from '../types'
import { formatTime, toastError } from '../ui'

const router = useRouter()
const detail = ref<FamilyDetail | null>(null)
const invites = ref<Invite[]>([])
const switchShow = ref(false)
const renameShow = ref(false)
const renameValue = ref('')
const dissolveShow = ref(false)
const dissolveValue = ref('')
const passwordShow = ref(false)
const oldPassword = ref('')
const newPassword = ref('')

const fid = () => session.currentFamilyId!
const switchActions = computed(() =>
  session.families.map((f) => ({
    name: f.name,
    id: f.id,
    color: f.id === session.currentFamilyId ? '#1989fa' : undefined,
  })),
)

async function load() {
  if (!session.currentFamilyId) return
  try {
    const [d, i] = await Promise.all([
      api.get<FamilyDetail>(`/families/${fid()}`),
      api.get<Invite[]>(`/families/${fid()}/invites`),
    ])
    detail.value = d
    invites.value = i
  } catch (e) {
    toastError(e)
  }
}
watch(() => session.currentFamilyId, load, { immediate: true })

function inviteLink(code: string) {
  return `${window.location.origin}/join/${code}`
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    showSuccessToast('已复制')
  } catch {
    showFailToast('复制失败，请长按手动复制')
  }
}

async function createInvite() {
  try {
    const invite = await api.post<Invite>(`/families/${fid()}/invites`)
    await load()
    await copy(inviteLink(invite.code))
  } catch (e) {
    toastError(e)
  }
}

async function revokeInvite(id: string) {
  try {
    await api.del(`/families/${fid()}/invites/${id}`)
    await load()
  } catch (e) {
    toastError(e)
  }
}

async function afterLeaving() {
  session.currentFamilyId = null
  await refreshFamilies()
  router.replace(session.families.length ? '/' : '/onboarding')
}

async function removeMember(id: string, username: string) {
  const isSelf = id === session.user?.id
  try {
    await showConfirmDialog({
      title: isSelf ? '退出家庭' : '移除成员',
      message: isSelf
        ? `确定退出「${detail.value?.name}」吗？如果你是最后一个成员，家庭里的所有数据都会被删除。`
        : `确定把 ${username} 移出这个家庭吗？`,
    })
  } catch {
    return
  }
  try {
    await api.del(`/families/${fid()}/members/${id}`)
    if (isSelf) await afterLeaving()
    else await load()
  } catch (e) {
    toastError(e)
  }
}

async function rename() {
  const name = renameValue.value.trim()
  if (!name) {
    showFailToast('请输入家庭名称')
    return
  }
  try {
    await api.patch(`/families/${fid()}`, { name })
    await refreshFamilies()
    await load()
  } catch (e) {
    toastError(e)
  }
}

async function dissolve() {
  if (dissolveValue.value.trim() !== detail.value?.name) {
    showFailToast('家庭名称不一致，没有解散')
    return
  }
  try {
    await api.del(`/families/${fid()}`)
    await afterLeaving()
  } catch (e) {
    toastError(e)
  }
}

async function changePassword() {
  if (newPassword.value.length < 8) {
    showFailToast('新密码至少 8 位')
    return
  }
  try {
    await api.post('/auth/password', { old_password: oldPassword.value, new_password: newPassword.value })
    showSuccessToast('密码已修改')
    oldPassword.value = ''
    newPassword.value = ''
  } catch (e) {
    toastError(e)
  }
}

function onSwitch(a: { id: string }) {
  setCurrentFamily(a.id)
}

async function logout() {
  try {
    await api.post('/auth/logout')
  } finally {
    clearSession()
    router.replace('/login')
  }
}
</script>

<template>
  <van-nav-bar title="家庭与我" />

  <van-cell-group inset title="当前家庭" style="margin-top: 4px">
    <van-cell
      :title="currentFamily()?.name"
      :value="session.families.length > 1 ? '切换' : ''"
      :is-link="session.families.length > 1"
      @click="session.families.length > 1 && (switchShow = true)"
    />
    <van-cell title="修改家庭名称" is-link @click="(renameValue = detail?.name ?? ''), (renameShow = true)" />
    <van-cell title="创建或加入其他家庭" is-link to="/onboarding" />
  </van-cell-group>

  <van-cell-group v-if="detail" inset :title="`成员（${detail.members.length}）`">
    <van-cell v-for="m in detail.members" :key="m.id" :title="m.username" :label="`加入于 ${formatTime(m.joined_at)}`">
      <template #right-icon>
        <van-button size="mini" :type="m.id === session.user?.id ? 'warning' : 'default'" @click="removeMember(m.id, m.username)">
          {{ m.id === session.user?.id ? '退出' : '移除' }}
        </van-button>
      </template>
    </van-cell>
  </van-cell-group>

  <van-cell-group inset title="邀请家人（链接 7 天内有效）">
    <van-cell v-for="inv in invites" :key="inv.id" :title="inviteLink(inv.code)" :label="`有效期至 ${formatTime(inv.expires_at)}`">
      <template #right-icon>
        <van-button size="mini" style="margin-right: 6px" @click="copy(inviteLink(inv.code))">复制</van-button>
        <van-button size="mini" type="danger" plain @click="revokeInvite(inv.id)">作废</van-button>
      </template>
    </van-cell>
    <van-cell title="生成新的邀请链接" icon="plus" is-link @click="createInvite" />
  </van-cell-group>

  <van-cell-group inset :title="`我（${session.user?.username}）`">
    <van-cell title="修改密码" is-link @click="passwordShow = true" />
    <van-cell title="退出登录" is-link @click="logout" />
  </van-cell-group>

  <div class="block-button">
    <van-button round block type="danger" plain @click="(dissolveValue = ''), (dissolveShow = true)">解散家庭</van-button>
  </div>

  <van-action-sheet
    v-model:show="switchShow"
    title="切换家庭"
    :actions="switchActions"
    cancel-text="取消"
    close-on-click-action
    @select="onSwitch"
  />

  <van-dialog v-model:show="renameShow" title="修改家庭名称" show-cancel-button @confirm="rename">
    <van-field v-model="renameValue" placeholder="家庭名称" maxlength="100" />
  </van-dialog>

  <van-dialog v-model:show="dissolveShow" title="解散家庭" show-cancel-button confirm-button-color="#ee0a24" @confirm="dissolve">
    <p class="hint">解散后，这个家庭的所有位置和物品都会被永久删除，所有成员都会被移出。请输入家庭名称「{{ detail?.name }}」确认：</p>
    <van-field v-model="dissolveValue" placeholder="家庭名称" />
  </van-dialog>

  <van-dialog v-model:show="passwordShow" title="修改密码" show-cancel-button @confirm="changePassword">
    <van-field v-model="oldPassword" type="password" label="原密码" autocomplete="current-password" />
    <van-field v-model="newPassword" type="password" label="新密码" placeholder="至少 8 位" autocomplete="new-password" />
  </van-dialog>
</template>
