using Microsoft.EntityFrameworkCore;

namespace CofRules.Core;

public sealed class CofRulesDbContext : DbContext
{
    public CofRulesDbContext(DbContextOptions<CofRulesDbContext> options) : base(options)
    {
    }

    public DbSet<Book> Books => Set<Book>();
    public DbSet<OutlineEntry> OutlineEntries => Set<OutlineEntry>();
    public DbSet<Section> Sections => Set<Section>();
    public DbSet<GameElement> GameElements => Set<GameElement>();
    public DbSet<GameElementTag> GameElementTags => Set<GameElementTag>();
    public DbSet<CrossRef> CrossRefs => Set<CrossRef>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Book>(entity =>
        {
            entity.ToTable("books");
            entity.HasKey(x => x.Id);
            entity.Property(x => x.Title).IsRequired();
            entity.HasIndex(x => x.Slug).IsUnique();
        });

        modelBuilder.Entity<OutlineEntry>(entity =>
        {
            entity.ToTable("outline_entries");
            entity.HasKey(x => x.Id);
            entity.HasIndex(x => new { x.BookId, x.SortOrder });
            entity.HasOne(x => x.Parent)
                .WithMany()
                .HasForeignKey(x => x.ParentId)
                .OnDelete(DeleteBehavior.Restrict);
        });

        modelBuilder.Entity<Section>(entity =>
        {
            entity.ToTable("sections");
            entity.HasKey(x => x.Id);
            entity.HasIndex(x => new { x.BookId, x.PageStart });
            entity.HasIndex(x => x.TitleNormalized);
        });

        modelBuilder.Entity<GameElement>(entity =>
        {
            entity.ToTable("game_elements");
            entity.HasKey(x => x.Id);
            entity.HasIndex(x => new { x.BookId, x.Kind, x.Slug }).IsUnique();
            entity.HasIndex(x => new { x.BookId, x.Kind, x.NameNormalized });
            entity.HasOne(x => x.Parent)
                .WithMany(x => x.Children)
                .HasForeignKey(x => x.ParentElementId)
                .OnDelete(DeleteBehavior.Restrict);
            entity.Property(x => x.DataJson).HasColumnType("TEXT");
            entity.Property(x => x.Body).HasColumnType("TEXT");
        });

        modelBuilder.Entity<GameElementTag>(entity =>
        {
            entity.ToTable("game_element_tags");
            entity.HasKey(x => new { x.GameElementId, x.Tag });
            entity.HasOne(x => x.GameElement)
                .WithMany(x => x.Tags)
                .HasForeignKey(x => x.GameElementId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<CrossRef>(entity =>
        {
            entity.ToTable("cross_refs");
            entity.HasKey(x => new { x.FromElementId, x.TargetKind, x.TargetName, x.Relation });
            entity.HasOne(x => x.From)
                .WithMany(x => x.Outgoing)
                .HasForeignKey(x => x.FromElementId)
                .OnDelete(DeleteBehavior.Cascade);
            entity.HasOne(x => x.To)
                .WithMany()
                .HasForeignKey(x => x.ToElementId)
                .OnDelete(DeleteBehavior.SetNull);
        });
    }

    public static CofRulesDbContext Open(string dbPath)
    {
        var full = Path.GetFullPath(dbPath);
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        var options = new DbContextOptionsBuilder<CofRulesDbContext>()
            .UseSqlite($"Data Source={full}")
            .Options;
        var db = new CofRulesDbContext(options);
        db.Database.EnsureCreated();
        db.EnsureSearchIndex();
        return db;
    }

    public void EnsureSearchIndex()
    {
        Database.ExecuteSqlRaw("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
              element_id UNINDEXED,
              kind,
              name,
              summary,
              body,
              tokenize = 'unicode61 remove_diacritics 2'
            );
            """);
        Database.ExecuteSqlRaw("""
            CREATE VIRTUAL TABLE IF NOT EXISTS section_search USING fts5(
              section_id UNINDEXED,
              title,
              summary,
              body,
              tokenize = 'unicode61 remove_diacritics 2'
            );
            """);
    }

    public void RebuildSearchIndex()
    {
        Database.ExecuteSqlRaw("DELETE FROM search_index;");
        Database.ExecuteSqlRaw("""
            INSERT INTO search_index(element_id, kind, name, summary, body)
            SELECT Id, Kind, Name, COALESCE(Summary, ''), Body FROM game_elements;
            """);
        Database.ExecuteSqlRaw("DELETE FROM section_search;");
        Database.ExecuteSqlRaw("""
            INSERT INTO section_search(section_id, title, summary, body)
            SELECT Id, Title, COALESCE(Summary, ''), Body FROM sections;
            """);
    }
}
