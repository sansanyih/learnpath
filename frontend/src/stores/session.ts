import { defineStore } from "pinia";
import { ref } from "vue";

import { api, getToken, setToken } from "@/api/request";
import type { TokenResponse, User } from "@/api/types";

export const useSessionStore = defineStore("session", () => {
  const token = ref<string>(getToken());
  const user = ref<User | null>(null);

  function persist(payload: TokenResponse): void {
    token.value = payload.token;
    user.value = payload.user;
    setToken(payload.token);
  }

  async function login(email: string, password: string): Promise<void> {
    const payload = await api.post<TokenResponse>("/api/auth/login", { email, password });
    persist(payload);
  }

  async function register(email: string, password: string, displayName?: string): Promise<void> {
    await api.post<User>("/api/auth/register", {
      email,
      password,
      display_name: displayName || null,
    });
    await login(email, password);
  }

  async function fetchMe(): Promise<User | null> {
    if (!token.value) return null;
    const me = await api.get<User>("/api/me");
    user.value = me;
    return me;
  }

  function logout(): void {
    token.value = "";
    user.value = null;
    setToken("");
  }

  return { token, user, login, register, fetchMe, logout };
});
