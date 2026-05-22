import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function AdminDashboardPage() {
  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>管理员首页</CardTitle>
          <CardDescription>这里是管理端预留入口，后续展示用户、课程、Agent、LLM 日志和系统健康状态。</CardDescription>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>权限边界</CardTitle>
          <CardDescription>学生端数据隔离由后端接口保证，前端守卫只负责路由体验。</CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
