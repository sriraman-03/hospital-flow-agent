import { zodResolver } from "@hookform/resolvers/zod";
import { Activity } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";

const schema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Password is required") });

export default function LoginPage() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  if (user) return <Navigate to="/" replace />;

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <Activity className="h-8 w-8 text-primary" aria-hidden />
          <CardTitle className="text-lg">Hospital Flow Agent</CardTitle>
          <p className="text-sm text-muted-foreground">Sign in to the operations console</p>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit(async (v) => { setError(null); try { await login(v.email, v.password); nav("/"); } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed"); } })}>
            <FormField label="Email" htmlFor="email" error={errors.email?.message}><Input id="email" type="email" autoComplete="username" {...register("email")} /></FormField>
            <FormField label="Password" htmlFor="password" error={errors.password?.message}><Input id="password" type="password" autoComplete="current-password" {...register("password")} /></FormField>
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Signing in…" : "Sign in"}</Button>
          </form>
          <p className="mt-4 text-xs text-muted-foreground">Synthetic demo data only. Authorised staff access; activity is audited. Operational tool, not a clinical system.</p>
        </CardContent>
      </Card>
    </div>
  );
}
