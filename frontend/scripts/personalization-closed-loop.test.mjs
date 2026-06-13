import assert from "node:assert/strict"
import fs from "node:fs"

const home = fs.readFileSync(new URL("../public/stitch-pages/home.html", import.meta.url), "utf8")
const pathProfile = fs.readFileSync(new URL("../public/stitch-pages/path-profile.html", import.meta.url), "utf8")
const api = fs.readFileSync(new URL("../public/stitch-pages/zhixue-static-api.js", import.meta.url), "utf8")

assert.doesNotMatch(home, />18\.5\s*</)
assert.doesNotMatch(home, />82%?</)
assert.match(home, /learningAnalyticsSummary/)
assert.match(home, /analytics-period/)
assert.match(home, /listLearningPaths/)
assert.doesNotMatch(home, /Dijkstra 算法/)
assert.doesNotMatch(home, /Lvl 12 \/ 65%/)
assert.match(api, /learning-analytics\/summary/)
assert.match(api, /learning-analytics\/sessions\/heartbeat/)
assert.match(api, /learning-paths/)

assert.match(pathProfile, /memory-status/)
assert.match(pathProfile, /memoryHealth/)
assert.match(pathProfile, /restoreMemory/)
assert.doesNotMatch(pathProfile, /overall \|\| 68/)

console.log("personalization closed loop contract ok")
