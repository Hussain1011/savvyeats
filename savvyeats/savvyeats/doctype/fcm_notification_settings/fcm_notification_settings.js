frappe.ui.form.on("FCM Notification Settings", {
  refresh: function(frm) {
    frm.add_custom_button("Send Test Notification", () => {
    	frm.trigger("send_notification");
 	 });
  },
  send_notification: function(frm){
      const d = new frappe.ui.Dialog({
        title: "Send Test Notification",
        fields: [
          {
            fieldname: "user",
            fieldtype: "Link",
            label: "User",
            options: "User",
            reqd: 1,
          },
          {
            fieldname: "title",
            fieldtype: "Data",
            label: "Title",
            reqd: 1,
          },
          {
            fieldname: "body",
            fieldtype: "Small Text",
            label: "Body",
            reqd: 1,
          },
        ],
        primary_action_label: "Send",
        primary_action: () => {
          const values = d.get_values();
          if (!values) return;

          frappe.call({
            method: "savvyeats.fcm.send_notification_to_user",
            args: {
              user: values.user,
              title: values.title,
              body: values.body,
            },
            freeze: true,
            freeze_message: "Sending...",
            callback: (r) => {
              d.hide();
              frappe.msgprint({
                title: "Sent",
                message: "Test notification sent successfully.",
                indicator: "green",
              });
            },
          });
        },
      });

      d.show();
  }
});