export default async function NdcPage({
  params,
  searchParams,
}: {
  params: Promise<{ ndc: string }>;
  searchParams: Promise<{ strict?: string }>;
}) {
  const { ndc } = await params;
  const query = await searchParams;
  return (
    <section>
      <h1 className="text-3xl font-semibold">Label of record</h1>
      <p className="mono mt-3 text-[#98a3b1]">
        {ndc}
        {query.strict === "1" ? " · strict mode" : ""}
      </p>
      <p className="mt-4 text-[#98a3b1]">The verdict view is filled in with the landed result.</p>
    </section>
  );
}
