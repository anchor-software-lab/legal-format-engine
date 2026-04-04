namespace LegalEngine.Api

open System
open System.IO
open Microsoft.AspNetCore.Builder
open Microsoft.AspNetCore.Http
open Microsoft.Extensions.DependencyInjection
open Microsoft.Extensions.FileProviders
open Microsoft.Extensions.Hosting

module Program =

    [<EntryPoint>]
    let main args =
        let builder = WebApplication.CreateBuilder(args)

        // Add services
        builder.Services.AddEndpointsApiExplorer() |> ignore
        builder.Services.AddCors(fun options ->
            options.AddDefaultPolicy(fun policy ->
                policy
                    .WithOrigins("https://localhost:8443", "https://localhost:3000", "null")
                    .AllowAnyMethod()
                    .AllowAnyHeader()
                    .AllowCredentials()
                |> ignore))
        |> ignore

        let app = builder.Build()

        // Middleware
        app.UseCors() |> ignore

        // Static file serving for word-addin/ directory
        let addinDir = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "word-addin", "src")
        if Directory.Exists(addinDir) then
            app.UseStaticFiles(
                StaticFileOptions(
                    FileProvider = new PhysicalFileProvider(Path.GetFullPath(addinDir)),
                    RequestPath = "/addin"))
            |> ignore

        // ── Route mapping ───────────────────────────────────────────

        // Health
        app.MapGet("/health", Func<IResult>(fun () ->
            RulesetsHandler.handleHealth ()))
        |> ignore

        // Rulesets
        app.MapGet("/rules/{jurisdiction}/{filingType}", Func<string, string, IResult>(fun jurisdiction filingType ->
            RulesetsHandler.handleGetRuleset jurisdiction filingType))
        |> ignore

        // Format / analyze filing
        app.MapPost("/analyze/filing", Func<FormatRequest, IResult>(fun req ->
            FormatHandler.handle req))
        |> ignore

        // Validate / analyze structure
        app.MapPost("/analyze/structure", Func<ValidateRequest, IResult>(fun req ->
            ValidateHandler.handle req))
        |> ignore

        // Generate caption
        app.MapPost("/generate/caption", Func<CaptionRequest, IResult>(fun req ->
            CaptionHandler.handle req))
        |> ignore

        app.Run()
        0
