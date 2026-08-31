import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Contract } from "../lib/types";
import { Card, StatusBadge, Loading, ErrorBox } from "../components/ui";

export default function Contracts() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["contracts"],
    queryFn: () => api.get<Contract[]>("/api/contracts"),
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Contratti</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">{data?.length || 0} contratti</p>
      </header>
      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 dark:border-slate-800 text-left text-xs uppercase text-slate-400">
              <th className="py-2">ID</th>
              <th>Nome</th>
              <th>Cliente</th>
              <th>WBS</th>
              <th>Tipo</th>
              <th>FY</th>
              <th>Stato</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((c) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/contracts/${c.id}`)}
                className="cursor-pointer border-b border-slate-50 hover:bg-brand-50"
              >
                <td className="py-2 font-medium text-brand-700">{c.id}</td>
                <td>{c.name}</td>
                <td>{c.client_name}</td>
                <td>{c.wbs_l1 || "-"}</td>
                <td>{c.contract_type}</td>
                <td>{c.fiscal_year || "-"}</td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
