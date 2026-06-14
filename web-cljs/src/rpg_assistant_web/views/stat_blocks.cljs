(ns rpg-assistant-web.views.stat-blocks
  (:require [clojure.string :as str]
            [rpg-assistant-web.state :as state]
            [rpg-assistant-web.views.common :as common]))

(defn- sorted-filtered [entries filter-text]
  (let [sorted (sort-by :name compare entries)
        query (str/trim (str/lower-case filter-text))]
    (if (seq query)
      (filter #(str/includes? (str/lower-case (:name %)) query) sorted)
      sorted)))

(defn- stat-block-card [document-id entry]
  (let [pages (:pages entry)]
    [:ui/a.card {:key (:chunk_id entry)
                 :ui/location {:location/page-id :pages/stat-block-detail
                               :location/params {:document-id document-id
                                                  :stat-block-name (:name entry)}}}
     [:h3 (:name entry)]
     [:p.muted
      (str "NC " (or (:nc entry) "—")
           " · p." (:start pages)
           (when (not= (:end pages) (:start pages))
             (str "–" (:end pages))))]]))

(defn stat-blocks-view [state document-id]
  (let [{:keys [entries loading? error]}
        (state/stat-blocks-state state document-id)
        filter-text (:stat-block-filter state)
        filtered (when entries (sorted-filtered entries filter-text))]
    (cond
      loading? (common/loading-view)
      error (common/error-view error)
      :else
      [:main.page
       [:h2 "Fiches COF2"]
       [:input {:type "search"
                :placeholder "Filtrer par nom…"
                :value filter-text
                :style {:width "100%"
                        :max-width "420px"
                        :padding "0.5rem"
                        :margin-bottom "1rem"
                        :border "1px solid var(--border)"
                        :border-radius "8px"}
                :on {:input [[:set-stat-block-filter :event/target.value]]}}]
       (if (empty? filtered)
         [:p.muted "Aucune fiche stat pour ce document."]
         [:div.card-grid
          (map #(stat-block-card document-id %) filtered)])])))
