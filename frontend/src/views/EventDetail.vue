<template>
  <el-card v-if="event">
    <h2>事件详情</h2>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="事件ID">{{ event.id }}</el-descriptions-item>
      <el-descriptions-item label="状态">{{ event.status }}</el-descriptions-item>
      <el-descriptions-item label="风险等级">{{ event.risk_level }}</el-descriptions-item>
      <el-descriptions-item label="类型">{{ event.event_type }}</el-descriptions-item>
      <el-descriptions-item label="开始时间">{{ event.start_time }}</el-descriptions-item>
      <el-descriptions-item label="停留秒数">{{ event.duration_seconds }}</el-descriptions-item>
    </el-descriptions>

    <h3 v-if="event.behavior_results?.length">人员行为</h3>
    <el-table v-if="event.behavior_results?.length" :data="event.behavior_results">
      <el-table-column prop="person_track_id" label="人员ID" />
      <el-table-column prop="behavior_label" label="行为" />
      <el-table-column prop="behavior_confidence" label="置信度" />
      <el-table-column prop="near_vehicle_seconds" label="车辆旁秒数" />
      <el-table-column prop="sequence_frame_count" label="序列帧数" />
      <el-table-column prop="model_type" label="模型类型" />
      <el-table-column prop="model_version" label="模型版本" />
    </el-table>

    <h3>关键帧</h3>
    <el-table :data="keyframes">
      <el-table-column prop="id" label="帧ID" />
      <el-table-column prop="frame_role" label="角色" />
      <el-table-column prop="timestamp" label="时间" />
      <el-table-column label="图片">
        <template #default="{ row }">
          <img v-if="frameUrls[row.id]" :src="frameUrls[row.id]" class="keyframe-image" alt="关键帧" />
          <span v-else>加载中</span>
        </template>
      </el-table-column>
    </el-table>

    <h3>模型结果</h3>
    <el-table :data="modelResults">
      <el-table-column prop="model_name" label="模型" />
      <el-table-column prop="model_type" label="类型" />
      <el-table-column prop="label" label="结果" />
      <el-table-column prop="score" label="置信度" />
    </el-table>

    <h3>人工复核</h3>
    <el-form label-width="100px">
      <el-form-item label="结论">
        <el-select v-model="review.result">
          <el-option label="异常" value="abnormal" />
          <el-option label="正常" value="normal" />
          <el-option label="无法判断" value="uncertain" />
        </el-select>
      </el-form-item>
      <el-form-item label="纠正类型">
        <el-input v-model="review.corrected_event_type" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="review.comment" type="textarea" />
      </el-form-item>
      <el-button type="primary" @click="submitReview">提交复核</el-button>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "../api/client";

const route = useRoute();
const event = ref<any>(null);
const keyframes = ref<any[]>([]);
const modelResults = ref<any[]>([]);
const frameUrls = ref<Record<string, string>>({});
const review = reactive({ result: "abnormal", corrected_event_type: "", comment: "" });

async function load() {
  const eventId = route.params.event_id as string;
  const responses = await Promise.all([
    api.get(`/events/${eventId}`),
    api.get(`/events/${eventId}/keyframes`),
    api.get(`/events/${eventId}/model-results`),
  ]);
  event.value = responses[0].data;
  keyframes.value = responses[1].data;
  modelResults.value = responses[2].data;
  await Promise.all(keyframes.value.map(async (frame) => {
    const response = await api.get(`/keyframes/${frame.id}/file`, { responseType: "blob" });
    frameUrls.value[frame.id] = URL.createObjectURL(response.data);
  }));
}

async function submitReview() {
  await api.post(`/events/${route.params.event_id}/review`, {
    reviewer_id: "reviewer",
    ...review,
  });
  ElMessage.success("复核完成");
  await load();
}

onMounted(load);

onBeforeUnmount(() => {
  Object.values(frameUrls.value).forEach(URL.revokeObjectURL);
});
</script>

<style scoped>
.keyframe-image {
  width: 180px;
  height: 100px;
  object-fit: cover;
  border-radius: 4px;
}
</style>
