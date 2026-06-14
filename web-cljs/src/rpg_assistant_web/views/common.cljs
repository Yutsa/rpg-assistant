(ns rpg-assistant-web.views.common)

(defn loading-view []
  [:main.page
   [:div.loading
    [:div.spinner]
    [:p.muted "Chargement…"]]])

(defn error-view [message & [{:keys [on-retry]}]]
  [:main.page
   [:div.state-box.error
    [:p message]
    (when on-retry
      [:button.btn {:on {:click [[on-retry]]}} "Réessayer"])]])

(defn empty-state-view [title & children]
  [:main.page
   (into [:div.state-box [:h2 title]] children)])
