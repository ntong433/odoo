/** @odoo-module **/

export async function openCurrentUserPreferences({ orm, actionService, userId }) {
    if (!Number.isInteger(userId) || userId <= 0) {
        throw new Error("Cannot open Preferences without an authenticated user record.");
    }
    const action = await orm.call("res.users", "action_get");
    action.res_id = userId;
    await actionService.doAction(action);
}
