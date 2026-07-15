import "../src/styles.css";

export const metadata = {
  title: "Jira Agent",
  description: "AI Jira assistant powered by Django and LangGraph",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
