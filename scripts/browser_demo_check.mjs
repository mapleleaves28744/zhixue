#!/usr/bin/env node

import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const frontendRequire = createRequire(path.join(REPO_ROOT, "frontend", "package.json"));
const { chromium } = frontendRequire("playwright");

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3000";
const DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1";
const DEFAULT_USERNAME = "student_demo";
const DEFAULT_PASSWORD = "StudentDemo2026!";

function parseArgs(argv) {
  const args = {
    frontendUrl: DEFAULT_FRONTEND_URL,
    apiUrl: DEFAULT_API_URL,
    username: DEFAULT_USERNAME,
    password: DEFAULT_PASSWORD,
    headed: false,
    screenshot: "output/playwright/demo-browser-check.png",
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--frontend-url") args.frontendUrl = argv[++index];
    else if (arg === "--api-url") args.apiUrl = argv[++index];
    else if (arg === "--username") args.username = argv[++index];
    else if (arg === "--password") args.password = argv[++index];
    else if (arg === "--headed") args.headed = true;
    else if (arg === "--screenshot") args.screenshot = argv[++index];
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    }
  }
  args.frontendUrl = args.frontendUrl.replace(/\/+$/, "");
  args.apiUrl = args.apiUrl.replace(/\/+$/, "");
  return args;
}

function printHelp() {
  console.log(`
Browser demo smoke check.

Prerequisites:
  1. Backend is running at --api-url
  2. Frontend is running at --frontend-url
  3. Run: python scripts/init_demo_student_data.py

Usage:
  npx --yes -p playwright node scripts/browser_demo_check.mjs \\
    --frontend-url http://127.0.0.1:3000 \\
    --api-url http://127.0.0.1:8000/api/v1
`);
}

async function apiRequest(apiUrl, pathName, options = {}) {
  const response = await fetch(`${apiUrl}${pathName}`, {
    ...options,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload || payload.code !== 0) {
    const detail = payload?.detail || payload?.message || response.statusText;
    throw new Error(`API ${pathName} failed: ${detail}`);
  }
  return payload.data;
}

async function loginAndLoadDemoCourse(args) {
  const token = await apiRequest(args.apiUrl, "/auth/login", {
    method: "POST",
    body: JSON.stringify({ username: args.username, password: args.password }),
  });
  const courses = await apiRequest(args.apiUrl, "/courses?page=1&page_size=50&status=active", {
    headers: { Authorization: `Bearer ${token.access_token}` },
  });
  const demoCourse = (courses.items || []).find((course) => course.course_code === "DS-DEMO");
  if (!demoCourse) {
    throw new Error("DS-DEMO course was not found. Run: python scripts/init_demo_student_data.py");
  }
  return { token, demoCourse };
}

async function assertFrameText(page, expected, label) {
  const frame = page.frameLocator("iframe.stitch-frame");
  await frame.getByText(expected, { exact: false }).first().waitFor({ timeout: 15_000 });
  console.log(`OK: ${label}`);
}

async function gotoAndAssert(page, args, route, expected, label) {
  await page.goto(`${args.frontendUrl}${route}`, { waitUntil: "domcontentloaded" });
  await assertFrameText(page, expected, label);
}

async function gotoPracticeAndAssert(page, args, route) {
  await page.goto(`${args.frontendUrl}${route}`, { waitUntil: "domcontentloaded" });
  const frame = page.frameLocator("iframe.stitch-frame");
  await frame.getByText("答题竞技", { exact: true }).click({ timeout: 15_000 });
  await assertFrameText(page, "顺序表最擅长的操作是", "practice page loads demo quiz");
}

async function ensureScreenshot(page, screenshotPath) {
  if (!screenshotPath) return;
  const absolutePath = path.isAbsolute(screenshotPath)
    ? screenshotPath
    : path.join(REPO_ROOT, screenshotPath);
  await fs.mkdir(path.dirname(absolutePath), { recursive: true });
  await page.screenshot({ path: absolutePath, fullPage: true });
  console.log(`screenshot: ${absolutePath}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { token, demoCourse } = await loginAndLoadDemoCourse(args);
  const storagePayload = {
    apiUrl: args.apiUrl,
    accessToken: token.access_token,
    refreshToken: token.refresh_token,
    user: token.user,
  };

  let browser;
  try {
    browser = await chromium.launch({ headless: !args.headed });
  } catch (error) {
    throw new Error(
      `Unable to launch Chromium. Install browser binaries with: npx playwright install chromium\n${error.message}`,
    );
  }

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    locale: "zh-CN",
  });
  await context.addInitScript((payload) => {
    window.localStorage.setItem("zhixue_api_base", payload.apiUrl);
    window.localStorage.setItem("access_token", payload.accessToken);
    window.localStorage.setItem("refresh_token", payload.refreshToken);
    window.localStorage.setItem("auth_user", JSON.stringify(payload.user));
  }, storagePayload);

  const page = await context.newPage();
  const courseQuery = `?course_id=${encodeURIComponent(demoCourse.id)}`;

  try {
    await gotoAndAssert(page, args, "/courses", "数据结构演示课", "courses page loads demo course");
    await gotoAndAssert(page, args, `/knowledge${courseQuery}`, "线性表学习 Wiki", "knowledge page loads demo Wiki");
    await gotoPracticeAndAssert(page, args, `/practice${courseQuery}`);
    await gotoAndAssert(page, args, `/dashboard${courseQuery}`, "基于你的最新画像/诊断", "dashboard shows active recommendations");
    await gotoAndAssert(page, args, `/path-profile${courseQuery}`, "自进化策略", "path-profile loads evolution section");
    await assertFrameText(page, "待确认", "path-profile shows draft strategy");
    await ensureScreenshot(page, args.screenshot);
  } finally {
    await context.close();
    await browser.close();
  }

  console.log(
    JSON.stringify(
      {
        status: "passed",
        username: args.username,
        course_id: demoCourse.id,
        course_code: demoCourse.course_code,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(`Browser demo check failed: ${error.message}`);
  process.exit(1);
});
