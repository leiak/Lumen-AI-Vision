import { defineStore } from "pinia";
import { api } from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("access_token") || "",
    user: null as any,
  }),
  actions: {
    async login(username: string, password: string) {
      const response = await api.post("/auth/login", { username, password });
      this.token = response.data.access_token;
      localStorage.setItem("access_token", this.token);
      await this.fetchMe();
    },
    async fetchMe() {
      if (!this.token) return;
      const response = await api.get("/auth/me");
      this.user = response.data;
    },
    logout() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("access_token");
    },
  },
});
