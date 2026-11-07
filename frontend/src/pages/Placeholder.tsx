import { Link } from "react-router-dom";

export default function Placeholder({ title, logo, text = "Not built yet. See docs/planning for the build order." }: { title: string; logo?: string; text?: string }) {
  return (
    <div className="card mx-auto max-w-2xl p-8 text-center">
      {logo ? <img src={logo} alt={title} className="mx-auto h-10 w-auto" /> : <h1 className="text-heading font-semibold">{title}</h1>}
      <p className="mt-4 text-body text-muted">{text}</p>
      <Link to="/" className="mt-6 inline-flex min-h-11 items-center rounded-panel bg-accent px-4 font-medium text-on-accent hover:bg-accent-hover">
        Back to the Hub
      </Link>
    </div>
  );
}
