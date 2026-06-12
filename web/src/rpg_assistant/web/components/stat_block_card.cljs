(ns rpg-assistant.web.components.stat-block-card
  (:require ["react-router-dom" :refer [Link]]
            [uix.core :refer [defui $]]))

(defn- page-label [^js entry]
  (let [pages (.-pages entry)]
    (if pages
      (let [start (.-start pages)
            end (.-end pages)]
        (str "p." start (when (not= end start) (str "–" end))))
      "p.—")))

(defui stat-block-card
  [{:keys [document-id entry]}]
  ($ Link {:class "card"
           :to (str "/documents/" document-id "/stat-blocks/"
                     (js/encodeURIComponent (.-name entry)))}
    ($ :h3 (.-name entry))
    ($ :p.muted
      (str "NC " (or (.-nc entry) "—") " · " (page-label entry)))))
