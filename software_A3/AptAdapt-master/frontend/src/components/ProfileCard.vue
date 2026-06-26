<template>
  <div class="profile-card">
    <p class="aa-kicker">Student Profile</p>
    <h2 class="aa-title">学生画像</h2>

    <div class="avatar-ring">
      <div class="avatar-core">徐</div>
    </div>

    <h3>{{ displayProfile.major }} · {{ displayProfile.grade }}</h3>
    <p class="goal">目标：{{ displayProfile.course_goal }}</p>

    <div class="tag-group">
      <span v-for="item in displayProfile.weak_points" :key="item" class="danger">{{ item }}</span>
      <span v-for="item in displayProfile.learning_preference" :key="item">{{ item }}</span>
      <span>{{ displayProfile.pace }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const mockProfile = {
  major: '计算机科学与技术',
  grade: '大二',
  course_goal: '两周内掌握 Cache、流水线和中断机制',
  weak_points: ['Cache 映射方式', '流水线冲突'],
  learning_preference: ['图解优先', '例题驱动', '代码示例'],
  pace: '每日 1h'
}

const displayProfile = computed(() => userStore.profile || mockProfile)
</script>

<style scoped>
.profile-card {
  padding: 18px;
  text-align: center;
}

.avatar-ring {
  width: 112px;
  height: 112px;
  margin: 18px auto 14px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  padding: 3px;
  background: conic-gradient(from 220deg, var(--aa-cyan), var(--aa-green), var(--aa-pink), var(--aa-cyan));
  box-shadow: 0 0 42px rgba(25, 191, 234, 0.2);
}

.avatar-core {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #fff;
  color: var(--aa-text);
  font-size: 40px;
  font-weight: 900;
}

h3 {
  margin: 0 0 10px;
  color: var(--aa-text);
  font-size: 16px;
}

.goal {
  margin: 0;
  color: var(--aa-muted);
  font-size: 13px;
  line-height: 1.7;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  min-width: 0;
}

.tag-group span {
  max-width: 100%;
  padding: 6px 9px;
  border-radius: 7px;
  color: #1b6c89;
  background: rgba(229, 249, 255, 0.78);
  border: 1px solid rgba(64, 184, 230, 0.18);
  font-size: 12px;
}

.tag-group .danger {
  color: #a75926;
  background: rgba(255, 245, 225, 0.88);
  border-color: rgba(255, 179, 64, 0.22);
}

@media (max-width: 900px) {
  .tag-group {
    gap: 7px;
  }

  .tag-group span {
    padding: 5px 7px;
    font-size: 11px;
  }
}
</style>
