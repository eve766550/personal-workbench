document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-confirm-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const confirmed = window.confirm("确定要删除这条骑行记录吗？删除后不能恢复。\n\n点击“确定”继续，点击“取消”保留记录。");
      if (!confirmed) {
        event.preventDefault();
      }
    });
  });
});

