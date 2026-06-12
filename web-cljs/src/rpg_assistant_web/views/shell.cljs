(ns rpg-assistant-web.views.shell
  (:require [rpg-assistant-web.routes :as routes]))

(defn breadcrumb-view [route]
  (let [items (routes/breadcrumbs route)]
    [:nav.breadcrumb {:aria-label "Fil d'Ariane"}
     (for [[index item] (map-indexed vector items)]
       [:span {:key (str (:label item) "-" index)}
        (when (pos? index) [:span {:aria-hidden true} " / "])
        (if-let [path (:path item)]
          [:a {:href path
               :on {:click [[:dom/prevent-default]
                            [:navigate path]]}}
           (:label item)]
          [:strong (:label item)])])]))

(defn shell-view [route body]
  [:div.app-shell
   [:header.app-header
    [:h1 "RPG Assistant"]
    [:span.badge "Replicant"]
    (breadcrumb-view route)]
   body])
