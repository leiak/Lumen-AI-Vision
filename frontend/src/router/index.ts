import { createRouter, createWebHistory } from "vue-router";
import EventList from "../views/EventList.vue";
import EventDetail from "../views/EventDetail.vue";
import Login from "../views/Login.vue";
import Tasks from "../views/Tasks.vue";
import Notifications from "../views/Notifications.vue";
import Metrics from "../views/Metrics.vue";

export default createRouter({
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
      path: "/login",
      name: "login",
      component: Login,
    },
  ],
});

router.beforeEach((to) => {
  const token = localStorage.getItem("access_token");
  if (to.name !== "login" && !token) {
    return { name: "login" };
  }
  return true;
});
