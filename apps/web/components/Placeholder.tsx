export function Placeholder({ title, body }: { title: string; body: string }) {
  return (
    <section>
      <h1 className="text-3xl font-semibold">{title}</h1>
      <p className="mt-3 max-w-2xl text-[#98a3b1]">{body}</p>
    </section>
  );
}
