import { Card } from "@/components/Card";

import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  return (
    <main>
      <h1>Sign in</h1>
      <Card title="EvalForge account">
        <LoginForm />
      </Card>
    </main>
  );
}
