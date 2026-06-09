"use client";

import { Segmented } from "@/components/ui/segmented";
import { useTheme } from "@/components/theme-provider";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <Segmented
      options={[
        { value: "light", label: "Light" },
        { value: "dark", label: "Dark" },
        { value: "system", label: "System" },
      ]}
      value={theme}
      onChange={setTheme}
    />
  );
}
