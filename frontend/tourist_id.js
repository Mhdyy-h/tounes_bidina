/**
 * Anonymous, client-generated tourist identity for the rewards system.
 * This app has no login anywhere - matching that, rewards points are tied
 * to a random id stored in this browser's localStorage, not an account.
 * Clearing site data resets a tourist's points; that's an accepted
 * trade-off for a no-signup demo, not an oversight.
 */
function getTouristId() {
  let id = localStorage.getItem("tg_tourist_id");
  if (!id) {
    id = "t_" + crypto.randomUUID();
    localStorage.setItem("tg_tourist_id", id);
  }
  return id;
}
