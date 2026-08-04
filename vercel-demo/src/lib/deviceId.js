export function getDeviceId() {
  let id = localStorage.getItem("quantdesk_device_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("quantdesk_device_id", id);
  }
  return id;
}
