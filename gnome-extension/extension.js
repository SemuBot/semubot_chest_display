// Turn off the gesture actions GNOME attaches to the stage (overview/workspace swipes, edge swipes).
export default class DisableGestures {
    enable() {
        this._actions = global.stage.get_actions().filter(a => a.enabled);
        this._actions.forEach(a => (a.enabled = false));
    }

    disable() {
        this._actions?.forEach(a => (a.enabled = true));
        this._actions = null;
    }
}
