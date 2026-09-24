import { createRouter, createWebHistory } from "vue-router";
import EventList from "../views/EventList.vue";
import EventDetail from "../views/EventDetail.vue";
import Login from "../views/Login.vue";
import Tasks from "../views/Tasks.vue";
import Notifications from "../views/Notifications.vue";
import Metrics from "../views/Metrics.vue";
import Admin from "../views/Admin.vue";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "events",
      component: EventList,
    },
    {
      path: "/events/:event_id",
      name: "event-detail",
      component: EventDetail,
    },
    {
      path: "/tasks",
      name: "tasks",
      component: Tasks,
    },
    {
      path: "/notifications",
      name: "notifications",
      component: Notifications,
    },
    {
      path: "/metrics",
      name: "metrics",
      component: Metrics,
    },
    {
      path: "/admin",
      name: "admin",
      component: Admin,
      meta: { roles: ["admin"] },
    },
    {
      path: "/login",
      name: "login",
      component: Login,
    },
  ],
});

export default router;

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  const token = localStorage.getItem("access_token");
  if (to.name !== "login" && !token) {
    return { name: "login" };
  }
  if (to.name !== "login" && !auth.user) {
    try {
      await auth.fetchMe();
    } catch {
      auth.logout();
      return { name: "login" };
    }
  }
  const roles = to.meta.roles as string[] | undefined;
  if (roles && !roles.includes(auth.user?.role)) {
    return { name: "events" };
  }
  return true;
});
