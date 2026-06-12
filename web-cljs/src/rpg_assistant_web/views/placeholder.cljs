(ns rpg-assistant-web.views.placeholder)

(defn placeholder-view [title subtitle]
  [:main.page
   [:div.state-box
    [:h2 title]
    [:p.muted subtitle]
    [:p.muted "Cette vue sera portée depuis le front React dans les prochaines itérations."]]])
