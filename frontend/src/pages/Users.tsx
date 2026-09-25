import { useQuery } from "@tanstack/react-query";
import { API } from "../api";

export default function Users() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["users"],
    queryFn: API.users,
  });

  return (
    <div>
      <h1>Users</h1>
      <p className="page-desc">
        Leads captured from the chat widget — names &amp; mobile numbers for the sales team to follow up.
      </p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Q count</th>
              <th>Registered</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={5} className="empty">Loading…</td></tr>
            )}
            {error && (
              <tr><td colSpan={5} className="empty error">{(error as Error).message}</td></tr>
            )}
            {!isLoading && !error && data?.length === 0 && (
              <tr><td colSpan={5} className="empty">No leads yet. Ask visitors to open the chat widget.</td></tr>
            )}
            {data?.map((u) => (
              <tr key={u.id}>
                <td className="table-text">{u.name}</td>
                <td>
                  <a href={`tel:${u.phone}`} className="table-link">{u.phone}</a>
                </td>
                <td>{u.message_count}</td>
                <td>{u.created_at ? new Date(u.created_at).toLocaleString() : "—"}</td>
                <td>{u.last_seen ? new Date(u.last_seen).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}