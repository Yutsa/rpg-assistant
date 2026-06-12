(ns rpg-assistant-web.views.shell
  (:require [rpg-assistant-web.router :as router]))

(defn breadcrumb-view [location]
  (let [items (router/breadcrumbs location)]
    [:nav.breadcrumb {:aria-label "Fil d'Ariane"}
     (for [[index item] (map-indexed vector items)]
       [:span {:key (str (:label item) "-" index)}
        (when (pos? index) [:span {:aria-hidden true} " / "])
        (if-let [loc (:location item)]
          [:ui/a {:ui/location loc} (:label item)]
          [:strong (:label item)])])]))

(defn shell-view [location body]
  [:div.app-shell
   [:header.app-header
    [:h1 "RPG Assistant"]
    [:span.badge "Replicant"]
    (breadcrumb-view location)]
   body])
