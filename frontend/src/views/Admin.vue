<template>
  <el-tabs v-model="activeTab">
    <el-tab-pane label="摄像头" name="cameras">
      <el-form inline>
        <el-form-item label="ID"><el-input v-model="cameraForm.id" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="cameraForm.name" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="cameraForm.location" /></el-form-item>
        <el-form-item label="流地址"><el-input v-model="cameraForm.stream_url" /></el-form-item>
        <el-form-item label="边缘节点"><el-input v-model="cameraForm.edge_node_id" /></el-form-item>
        <el-button type="primary" @click="createCamera">新增</el-button>
      </el-form>
      <el-table :data="cameras">
        <el-table-column prop="id" label="ID" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="location" label="位置" />
        <el-table-column prop="stream_url" label="流地址" />
        <el-table-column prop="status" label="状态" />
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="toggleCamera(row)">{{ row.status === 'online' ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="区域" name="areas">
      <el-form inline>
        <el-form-item label="ID"><el-input v-model="areaForm.id" /></el-form-item>
        <el-form-item label="摄像头"><el-select v-model="areaForm.camera_id"><el-option v-for="camera in cameras" :key="camera.id" :label="camera.name" :value="camera.id" /></el-select></el-form-item>
        <el-form-item label="名称"><el-input v-model="areaForm.name" /></el-form-item>
        <el-form-item label="多边形"><el-input v-model="areaForm.polygon" /></el-form-item>
        <el-form-item label="停留秒"><el-input-number v-model="areaForm.stay_threshold_seconds" :min="1" /></el-form-item>
        <el-form-item label="高风险秒"><el-input-number v-model="areaForm.high_risk_seconds" :min="2" /></el-form-item>
        <el-button type="primary" @click="createArea">新增</el-button>
      </el-form>
      <el-table :data="areas">
        <el-table-column prop="id" label="ID" />
        <el-table-column prop="camera_id" label="摄像头" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="stay_threshold_seconds" label="停留阈值" />
        <el-table-column prop="high_risk_seconds" label="高风险阈值" />
        <el-table-column prop="enabled" label="启用" />
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="toggleArea(row)">{{ row.enabled ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="用户" name="users">
      <el-form inline>
        <el-form-item label="用户名"><el-input v-model="userForm.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="userForm.password" type="password" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="userForm.full_name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role">
            <el-option label="管理员" value="admin" />
            <el-option label="安保" value="security" />
            <el-option label="操作员" value="operator" />
            <el-option label="查看者" value="viewer" />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="createUser">新增</el-button>
      </el-form>
      <el-table :data="users">
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="full_name" label="姓名" />
        <el-table-column prop="role" label="角色" />
        <el-table-column prop="is_active" label="启用" />
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="toggleUser(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="审计" name="audit">
      <el-table :data="auditLogs">
        <el-table-column prop="created_at" label="时间" />
        <el-table-column prop="user_id" label="用户" />
        <el-table-column prop="action" label="动作" />
        <el-table-column prop="resource_type" label="资源" />
        <el-table-column prop="resource_id" label="资源ID" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="样本" name="samples">
      <el-table :data="samples">
        <el-table-column prop="created_at" label="时间" />
        <el-table-column prop="event_id" label="事件" />
        <el-table-column prop="label" label="标签" />
        <el-table-column prop="risk_level" label="风险" />
        <el-table-column prop="reviewer_id" label="复核人" />
        <el-table-column prop="used_for_training" label="已训练" />
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="数据导出" name="exports">
      <el-alert type="info" :closable="false" title="导出 CSV 格式数据，按时间倒序导出最近 10000~50000 行" />
      <div class="export-actions">
        <el-button type="primary" @click="exportEvents">导出事件 CSV</el-button>
        <el-button type="success" @click="exportMetrics">导出模型结果 CSV</el-button>
        <el-button v-if="auth.user?.role === 'admin'" type="warning" @click="exportAuditLogs">导出审计日志 CSV</el-button>
      </div>
      <p class="export-hint">审计日志导出仅对管理员可见，请妥善保存并遵守数据合规要求。</p>
    </el-tab-pane>
  </el-tabs>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";
import { useAuthStore } from "../stores/auth";
import { api } from "../api/client";

const auth = useAuthStore();

const activeTab = ref("cameras");
const cameras = ref<any[]>([]);
const areas = ref<any[]>([]);
const users = ref<any[]>([]);
const auditLogs = ref<any[]>([]);
const samples = ref<any[]>([]);
const cameraForm = reactive({ id: "", name: "", location: "", stream_url: "", edge_node_id: "" });
const areaForm = reactive({
  id: "",
  camera_id: "",
  name: "",
  polygon: "[[120,130],[1120,130],[1120,620],[120,620]]",
  stay_threshold_seconds: 300,
  high_risk_seconds: 600,
});
const userForm = reactive({ username: "", password: "", full_name: "", role: "viewer" });

async function load() {
  const [cameraResponse, areaResponse] = await Promise.all([
    api.get("/cameras"),
    api.get("/areas"),
  ]);
  cameras.value = cameraResponse.data;
  areas.value = areaResponse.data;
  const [usersResponse, auditResponse, sampleResponse] = await Promise.all([
    api.get("/users"),
    api.get("/audit-logs"),
    api.get("/training-samples"),
  ]);
  users.value = usersResponse.data;
  auditLogs.value = auditResponse.data;
  samples.value = sampleResponse.data;
}

async function createCamera() {
  await api.post("/cameras", cameraForm);
  ElMessage.success("摄像头已创建");
  await load();
}

async function toggleCamera(row: any) {
  await api.patch(`/cameras/${row.id}`, { status: row.status === "online" ? "offline" : "online" });
  await load();
}

async function createArea() {
  const payload = {
    ...areaForm,
    polygon: JSON.parse(areaForm.polygon),
  };
  await api.post("/areas", payload);
  ElMessage.success("区域已创建");
  await load();
}

async function toggleArea(row: any) {
  await api.patch(`/areas/${row.id}`, { enabled: !row.enabled });
  await load();
}

async function createUser() {
  await api.post("/users", userForm);
  ElMessage.success("用户已创建");
  await load();
}

async function toggleUser(row: any) {
  await api.patch(`/users/${row.id}`, { is_active: !row.is_active });
  await load();
}

async function exportEvents() {
  const response = await api.get("/exports/events", { responseType: "blob" });
  downloadBlob(response.data, response.headers["content-disposition"]?.split("filename=")[1]?.replace(/"/g, "") || "events.csv");
  ElMessage.success("事件 CSV 已下载");
}

async function exportMetrics() {
  const response = await api.get("/exports/metrics", { responseType: "blob" });
  downloadBlob(response.data, response.headers["content-disposition"]?.split("filename=")[1]?.replace(/"/g, "") || "metrics.csv");
  ElMessage.success("模型结果 CSV 已下载");
}

async function exportAuditLogs() {
  if (auth.user?.role !== "admin") {
    ElMessage.warning("仅管理员可导出审计日志");
    return;
  }
  const response = await api.get("/exports/audit-logs", { responseType: "blob" });
  downloadBlob(response.data, response.headers["content-disposition"]?.split("filename=")[1]?.replace(/"/g, "") || "audit-logs.csv");
  ElMessage.success("审计日志 CSV 已下载");
}

function downloadBlob(data: BlobPart, filename: string) {
  const url = window.URL.createObjectURL(new Blob([data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

onMounted(load);
</script>

<style scoped>
.export-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}
.export-hint {
  margin-top: 12px;
  color: #909399;
  font-size: 12px;
}
</style>
