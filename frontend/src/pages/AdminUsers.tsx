import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useFlash } from "../lib/flash";

export function AdminUsers() {
  const { user: me } = useAuth();
  const { flash } = useFlash();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [search, setSearch] = useState(q);
  const [users, setUsers] = useState<User[] | null>(null);

  const load = useCallback(async () => {
    const res = await api.get<{ users: User[] }>(`/api/admin/users?q=${encodeURIComponent(q)}`);
    if (res.ok) setUsers(res.data.users);
  }, [q]);

  useEffect(() => {
    setSearch(q);
    void load();
  }, [q, load]);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    setParams(search ? { q: search } : {});
  }

  async function act(u: User, action: "toggle-ban" | "toggle-role", question: string) {
    if (!window.confirm(question)) return;
    const res = await api.post<{ message: string }>(`/api/admin/users/${u.id}/${action}`);
    flash(res.ok ? "success" : "error", res.data.message ?? res.data.error ?? "Something went wrong.");
    await load();
  }

  return (
    <section className="card">
      <h1>User management</h1>
      <form className="row" onSubmit={onSearch} role="search">
        <label htmlFor="user-search" className="sr-only">Search users</label>
        <input id="user-search" type="search" placeholder="Search by name or email" value={search}
          onChange={(e) => setSearch(e.target.value)} />
        <button type="submit" className="btn">Search</button>
      </form>

      {users === null ? (
        <p className="muted">Loading…</p>
      ) : users.length === 0 ? (
        <p className="muted" data-testid="empty-state">No users match “{q}”.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = u.id === me?.id;
                const status = u.is_banned ? "Banned" : u.is_verified ? "Active" : "Unverified";
                return (
                  <tr key={u.id} data-testid="user-row" data-email={u.email}>
                    <td>{u.name}{isMe && <span className="muted"> (you)</span>}</td>
                    <td>{u.email}</td>
                    <td>{u.role === "admin" ? "Admin" : "User"}</td>
                    <td><span className={`pill ${status.toLowerCase()}`} data-testid="user-status">{status}</span></td>
                    <td className="actions">
                      {!isMe && (
                        <>
                          <button type="button" className="btn small ghost"
                            onClick={() => act(u, "toggle-role", `Change the role of ${u.email}?`)}>
                            {u.role === "admin" ? "Remove admin" : "Make admin"}
                          </button>
                          <button type="button" className={`btn small ${u.is_banned ? "ghost" : "danger"}`}
                            onClick={() => act(u, "toggle-ban", `${u.is_banned ? "Unban" : "Ban"} ${u.email}?`)}>
                            {u.is_banned ? "Unban" : "Ban"}
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
