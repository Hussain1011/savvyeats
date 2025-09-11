// // Copyright (c) 2021, Blue Lynx and contributors
// // For license information, please see license.txt

// frappe.ui.form.on('Payment Log', {
//     refresh: function(frm) {

//             //Update payment manually
//             if (frm.doc.payment_updated == 0) {
//                 frm.add_custom_button(__('Update payment manually'), function() {
//                     frappe.call({
//                         method: 'club_api.payments.doctype.payment_log.payment_log.update_payment_manual',
//                         args: { doc_id: frm.doc.name },
//                         callback: function(r) {
//                             cur_frm.reload_doc();
//                         }
//                     });
//                     // frm.save()
//                 });
//             }
//         }
//         // }
// });