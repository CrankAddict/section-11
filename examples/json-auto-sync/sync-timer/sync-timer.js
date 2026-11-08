// Paste this entire ES module into your Cloudflare Worker's dashboard editor.
const MAX_ATTEMPTS = 3;
const REQUEST_TIMEOUT_MS = 10_000;
const MAX_WAIT_MS = 5_000;

function configuration(env) {
  const token = env?.GITHUB_TOKEN;
  const repository = env?.GITHUB_REPOSITORY;
  const ref = env?.GITHUB_REF === undefined ? "main" : env.GITHUB_REF;
  if (typeof token !== "string" || !token || /[^\x21-\x7e]/.test(token)) {
    throw new Error("Sync timer: invalid GITHUB_TOKEN (use a nonempty secret without whitespace)");
  }
  if (typeof repository !== "string" || repository.trim() !== repository ||
      !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}$/.test(repository) ||
      [".", ".."].includes(repository.split("/")[1])) {
    throw new Error("Sync timer: invalid GITHUB_REPOSITORY (use owner/name)");
  }
  if (typeof ref !== "string" || !ref || ref.length > 1024 || ref === "@" ||
      /[\x00-\x20\x7f~^:?*\[\\]/.test(ref) || ref.includes("..") || ref.includes("@{") ||
      ref.split("/").some(part => !part || part.startsWith(".") ||
        part.endsWith(".") || part.endsWith(".lock"))) {
    throw new Error("Sync timer: invalid GITHUB_REF (use the default branch name)");
  }
  return { token, repository, ref };
}

function retryDelay(headers, attempt) {
  let delay = 1000 * attempt;
  const retryAfter = headers.get("Retry-After");
  if (retryAfter !== null) {
    let wait;
    if (/^\d+$/.test(retryAfter)) {
      wait = Number(retryAfter) * 1000;
    } else if (/^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT$/.test(retryAfter)) {
      wait = Date.parse(retryAfter) - Date.now();
    } else {
      return Infinity; // An unreadable server hold is not permission to retry.
    }
    if (!Number.isFinite(wait)) return Infinity;
    delay = Math.max(delay, wait);
  }
  if (headers.get("X-RateLimit-Remaining") === "0") {
    const reset = headers.get("X-RateLimit-Reset");
    if (reset === null || !/^\d+$/.test(reset)) return Infinity;
    const wait = Number(reset) * 1000 - Date.now();
    if (!Number.isFinite(wait)) return Infinity;
    delay = Math.max(delay, wait);
  }
  return delay;
}

async function dispatch(env) {
  const { token, repository, ref } = configuration(env);
  const url = `https://api.github.com/repos/${repository}/actions/workflows/auto-sync.yml/dispatches`;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    const controller = new AbortController();
    let timeout;
    let timedOut = false;
    let response;
    let cause;
    try {
      const deadline = new Promise((_, reject) => {
        timeout = setTimeout(() => {
          timedOut = true;
          controller.abort();
          reject(new Error("request timeout"));
        }, REQUEST_TIMEOUT_MS);
      });
      response = await Promise.race([
        fetch(url, {
          method: "POST",
          redirect: "manual",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "section11-sync-timer",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ ref, inputs: { operation: "Sync timer" } }),
          signal: controller.signal,
        }),
        deadline,
      ]);
    } catch {
      // Transport errors can contain request details. Never expose the original.
      cause = timedOut ? "request timeout" : "network error";
    } finally {
      clearTimeout(timeout);
    }

    let delay = 1000 * attempt;
    if (response) {
      const status = response.status;
      console.log(status);
      // No response body is needed, including error bodies that may echo inputs.
      if (response.body) response.body.cancel().catch(() => {});
      if (status >= 200 && status < 300) return;
      cause = `HTTP ${status}`;
      // Even rate-limited 403/429 responses end this tick: only 5xx is retried.
      if (status < 500 || status > 599) throw new Error(`Sync timer: ${cause}`);
      delay = retryDelay(response.headers, attempt);
    }
    if (attempt === MAX_ATTEMPTS || delay > MAX_WAIT_MS) {
      throw new Error(`Sync timer: ${cause}`);
    }
    // At most two waits of 5 seconds plus three requests of 10 seconds.
    await new Promise(resolve => setTimeout(resolve, delay));
  }
}

export default {
  async scheduled(_event, env) {
    await dispatch(env);
  },
  fetch() {
    return new Response("Not found", { status: 404 });
  },
};
