import { Placeholder } from "@/components/Placeholder";

export default async function FactPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Placeholder
      title="Safety fact"
      body={`Census, copy lag and source hubs for ${id} appear here once the graph-wide views are served.`}
    />
  );
}
