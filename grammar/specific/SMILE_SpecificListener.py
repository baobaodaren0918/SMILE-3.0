# Generated from SMILE_Specific.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SMILE_SpecificParser import SMILE_SpecificParser
else:
    from SMILE_SpecificParser import SMILE_SpecificParser

# This class defines a complete listener for a parse tree produced by SMILE_SpecificParser.
class SMILE_SpecificListener(ParseTreeListener):

    # Enter a parse tree produced by SMILE_SpecificParser#migration.
    def enterMigration(self, ctx:SMILE_SpecificParser.MigrationContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#migration.
    def exitMigration(self, ctx:SMILE_SpecificParser.MigrationContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#header.
    def enterHeader(self, ctx:SMILE_SpecificParser.HeaderContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#header.
    def exitHeader(self, ctx:SMILE_SpecificParser.HeaderContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#migrationDecl.
    def enterMigrationDecl(self, ctx:SMILE_SpecificParser.MigrationDeclContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#migrationDecl.
    def exitMigrationDecl(self, ctx:SMILE_SpecificParser.MigrationDeclContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#evolutionDecl.
    def enterEvolutionDecl(self, ctx:SMILE_SpecificParser.EvolutionDeclContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#evolutionDecl.
    def exitEvolutionDecl(self, ctx:SMILE_SpecificParser.EvolutionDeclContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#fromToDecl.
    def enterFromToDecl(self, ctx:SMILE_SpecificParser.FromToDeclContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#fromToDecl.
    def exitFromToDecl(self, ctx:SMILE_SpecificParser.FromToDeclContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#usingDecl.
    def enterUsingDecl(self, ctx:SMILE_SpecificParser.UsingDeclContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#usingDecl.
    def exitUsingDecl(self, ctx:SMILE_SpecificParser.UsingDeclContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#databaseType.
    def enterDatabaseType(self, ctx:SMILE_SpecificParser.DatabaseTypeContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#databaseType.
    def exitDatabaseType(self, ctx:SMILE_SpecificParser.DatabaseTypeContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#version.
    def enterVersion(self, ctx:SMILE_SpecificParser.VersionContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#version.
    def exitVersion(self, ctx:SMILE_SpecificParser.VersionContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#operation.
    def enterOperation(self, ctx:SMILE_SpecificParser.OperationContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#operation.
    def exitOperation(self, ctx:SMILE_SpecificParser.OperationContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_property.
    def enterAdd_property(self, ctx:SMILE_SpecificParser.Add_propertyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_property.
    def exitAdd_property(self, ctx:SMILE_SpecificParser.Add_propertyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#propertyClause.
    def enterPropertyClause(self, ctx:SMILE_SpecificParser.PropertyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#propertyClause.
    def exitPropertyClause(self, ctx:SMILE_SpecificParser.PropertyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withTypeClause.
    def enterWithTypeClause(self, ctx:SMILE_SpecificParser.WithTypeClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withTypeClause.
    def exitWithTypeClause(self, ctx:SMILE_SpecificParser.WithTypeClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withDefaultClause.
    def enterWithDefaultClause(self, ctx:SMILE_SpecificParser.WithDefaultClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withDefaultClause.
    def exitWithDefaultClause(self, ctx:SMILE_SpecificParser.WithDefaultClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#notNullClause.
    def enterNotNullClause(self, ctx:SMILE_SpecificParser.NotNullClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#notNullClause.
    def exitNotNullClause(self, ctx:SMILE_SpecificParser.NotNullClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_foreign_key.
    def enterAdd_foreign_key(self, ctx:SMILE_SpecificParser.Add_foreign_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_foreign_key.
    def exitAdd_foreign_key(self, ctx:SMILE_SpecificParser.Add_foreign_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#constraintClause.
    def enterConstraintClause(self, ctx:SMILE_SpecificParser.ConstraintClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#constraintClause.
    def exitConstraintClause(self, ctx:SMILE_SpecificParser.ConstraintClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_embedded.
    def enterAdd_embedded(self, ctx:SMILE_SpecificParser.Add_embeddedContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_embedded.
    def exitAdd_embedded(self, ctx:SMILE_SpecificParser.Add_embeddedContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#embeddedClause.
    def enterEmbeddedClause(self, ctx:SMILE_SpecificParser.EmbeddedClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#embeddedClause.
    def exitEmbeddedClause(self, ctx:SMILE_SpecificParser.EmbeddedClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withStructureClause.
    def enterWithStructureClause(self, ctx:SMILE_SpecificParser.WithStructureClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withStructureClause.
    def exitWithStructureClause(self, ctx:SMILE_SpecificParser.WithStructureClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_entity.
    def enterAdd_entity(self, ctx:SMILE_SpecificParser.Add_entityContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_entity.
    def exitAdd_entity(self, ctx:SMILE_SpecificParser.Add_entityContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#entityClause.
    def enterEntityClause(self, ctx:SMILE_SpecificParser.EntityClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#entityClause.
    def exitEntityClause(self, ctx:SMILE_SpecificParser.EntityClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withKeyClause.
    def enterWithKeyClause(self, ctx:SMILE_SpecificParser.WithKeyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withKeyClause.
    def exitWithKeyClause(self, ctx:SMILE_SpecificParser.WithKeyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_primary_key.
    def enterAdd_primary_key(self, ctx:SMILE_SpecificParser.Add_primary_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_primary_key.
    def exitAdd_primary_key(self, ctx:SMILE_SpecificParser.Add_primary_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_unique_key.
    def enterAdd_unique_key(self, ctx:SMILE_SpecificParser.Add_unique_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_unique_key.
    def exitAdd_unique_key(self, ctx:SMILE_SpecificParser.Add_unique_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_partition_key.
    def enterAdd_partition_key(self, ctx:SMILE_SpecificParser.Add_partition_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_partition_key.
    def exitAdd_partition_key(self, ctx:SMILE_SpecificParser.Add_partition_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_clustering_key.
    def enterAdd_clustering_key(self, ctx:SMILE_SpecificParser.Add_clustering_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_clustering_key.
    def exitAdd_clustering_key(self, ctx:SMILE_SpecificParser.Add_clustering_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_label.
    def enterAdd_label(self, ctx:SMILE_SpecificParser.Add_labelContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_label.
    def exitAdd_label(self, ctx:SMILE_SpecificParser.Add_labelContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#keyColumns.
    def enterKeyColumns(self, ctx:SMILE_SpecificParser.KeyColumnsContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#keyColumns.
    def exitKeyColumns(self, ctx:SMILE_SpecificParser.KeyColumnsContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#keyClause.
    def enterKeyClause(self, ctx:SMILE_SpecificParser.KeyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#keyClause.
    def exitKeyClause(self, ctx:SMILE_SpecificParser.KeyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#referencesClause.
    def enterReferencesClause(self, ctx:SMILE_SpecificParser.ReferencesClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#referencesClause.
    def exitReferencesClause(self, ctx:SMILE_SpecificParser.ReferencesClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withColumnsClause.
    def enterWithColumnsClause(self, ctx:SMILE_SpecificParser.WithColumnsClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withColumnsClause.
    def exitWithColumnsClause(self, ctx:SMILE_SpecificParser.WithColumnsClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_property.
    def enterDelete_property(self, ctx:SMILE_SpecificParser.Delete_propertyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_property.
    def exitDelete_property(self, ctx:SMILE_SpecificParser.Delete_propertyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_foreign_key.
    def enterDelete_foreign_key(self, ctx:SMILE_SpecificParser.Delete_foreign_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_foreign_key.
    def exitDelete_foreign_key(self, ctx:SMILE_SpecificParser.Delete_foreign_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_embedded.
    def enterDelete_embedded(self, ctx:SMILE_SpecificParser.Delete_embeddedContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_embedded.
    def exitDelete_embedded(self, ctx:SMILE_SpecificParser.Delete_embeddedContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_entity.
    def enterDelete_entity(self, ctx:SMILE_SpecificParser.Delete_entityContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_entity.
    def exitDelete_entity(self, ctx:SMILE_SpecificParser.Delete_entityContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_primary_key.
    def enterDelete_primary_key(self, ctx:SMILE_SpecificParser.Delete_primary_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_primary_key.
    def exitDelete_primary_key(self, ctx:SMILE_SpecificParser.Delete_primary_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_unique_key.
    def enterDelete_unique_key(self, ctx:SMILE_SpecificParser.Delete_unique_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_unique_key.
    def exitDelete_unique_key(self, ctx:SMILE_SpecificParser.Delete_unique_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_partition_key.
    def enterDelete_partition_key(self, ctx:SMILE_SpecificParser.Delete_partition_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_partition_key.
    def exitDelete_partition_key(self, ctx:SMILE_SpecificParser.Delete_partition_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_clustering_key.
    def enterDelete_clustering_key(self, ctx:SMILE_SpecificParser.Delete_clustering_keyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_clustering_key.
    def exitDelete_clustering_key(self, ctx:SMILE_SpecificParser.Delete_clustering_keyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_label.
    def enterDelete_label(self, ctx:SMILE_SpecificParser.Delete_labelContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_label.
    def exitDelete_label(self, ctx:SMILE_SpecificParser.Delete_labelContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#rename_property.
    def enterRename_property(self, ctx:SMILE_SpecificParser.Rename_propertyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#rename_property.
    def exitRename_property(self, ctx:SMILE_SpecificParser.Rename_propertyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#rename_entity.
    def enterRename_entity(self, ctx:SMILE_SpecificParser.Rename_entityContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#rename_entity.
    def exitRename_entity(self, ctx:SMILE_SpecificParser.Rename_entityContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#flatten.
    def enterFlatten(self, ctx:SMILE_SpecificParser.FlattenContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#flatten.
    def exitFlatten(self, ctx:SMILE_SpecificParser.FlattenContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#unflatten.
    def enterUnflatten(self, ctx:SMILE_SpecificParser.UnflattenContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#unflatten.
    def exitUnflatten(self, ctx:SMILE_SpecificParser.UnflattenContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#unnest.
    def enterUnnest(self, ctx:SMILE_SpecificParser.UnnestContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#unnest.
    def exitUnnest(self, ctx:SMILE_SpecificParser.UnnestContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#unnestCarryList.
    def enterUnnestCarryList(self, ctx:SMILE_SpecificParser.UnnestCarryListContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#unnestCarryList.
    def exitUnnestCarryList(self, ctx:SMILE_SpecificParser.UnnestCarryListContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#unnestCarryField.
    def enterUnnestCarryField(self, ctx:SMILE_SpecificParser.UnnestCarryFieldContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#unnestCarryField.
    def exitUnnestCarryField(self, ctx:SMILE_SpecificParser.UnnestCarryFieldContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#unnestFieldList.
    def enterUnnestFieldList(self, ctx:SMILE_SpecificParser.UnnestFieldListContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#unnestFieldList.
    def exitUnnestFieldList(self, ctx:SMILE_SpecificParser.UnnestFieldListContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#SimpleField.
    def enterSimpleField(self, ctx:SMILE_SpecificParser.SimpleFieldContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#SimpleField.
    def exitSimpleField(self, ctx:SMILE_SpecificParser.SimpleFieldContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#NestedField.
    def enterNestedField(self, ctx:SMILE_SpecificParser.NestedFieldContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#NestedField.
    def exitNestedField(self, ctx:SMILE_SpecificParser.NestedFieldContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#unwind.
    def enterUnwind(self, ctx:SMILE_SpecificParser.UnwindContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#unwind.
    def exitUnwind(self, ctx:SMILE_SpecificParser.UnwindContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#wind.
    def enterWind(self, ctx:SMILE_SpecificParser.WindContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#wind.
    def exitWind(self, ctx:SMILE_SpecificParser.WindContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#nest.
    def enterNest(self, ctx:SMILE_SpecificParser.NestContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#nest.
    def exitNest(self, ctx:SMILE_SpecificParser.NestContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#copy_property.
    def enterCopy_property(self, ctx:SMILE_SpecificParser.Copy_propertyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#copy_property.
    def exitCopy_property(self, ctx:SMILE_SpecificParser.Copy_propertyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#copy_entity.
    def enterCopy_entity(self, ctx:SMILE_SpecificParser.Copy_entityContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#copy_entity.
    def exitCopy_entity(self, ctx:SMILE_SpecificParser.Copy_entityContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#move_property.
    def enterMove_property(self, ctx:SMILE_SpecificParser.Move_propertyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#move_property.
    def exitMove_property(self, ctx:SMILE_SpecificParser.Move_propertyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#merge.
    def enterMerge(self, ctx:SMILE_SpecificParser.MergeContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#merge.
    def exitMerge(self, ctx:SMILE_SpecificParser.MergeContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#split.
    def enterSplit(self, ctx:SMILE_SpecificParser.SplitContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#split.
    def exitSplit(self, ctx:SMILE_SpecificParser.SplitContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#splitPart.
    def enterSplitPart(self, ctx:SMILE_SpecificParser.SplitPartContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#splitPart.
    def exitSplitPart(self, ctx:SMILE_SpecificParser.SplitPartContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#cast_property.
    def enterCast_property(self, ctx:SMILE_SpecificParser.Cast_propertyContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#cast_property.
    def exitCast_property(self, ctx:SMILE_SpecificParser.Cast_propertyContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#cast_constraint.
    def enterCast_constraint(self, ctx:SMILE_SpecificParser.Cast_constraintContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#cast_constraint.
    def exitCast_constraint(self, ctx:SMILE_SpecificParser.Cast_constraintContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#add_constraint.
    def enterAdd_constraint(self, ctx:SMILE_SpecificParser.Add_constraintContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#add_constraint.
    def exitAdd_constraint(self, ctx:SMILE_SpecificParser.Add_constraintContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#ConstraintBodyReference.
    def enterConstraintBodyReference(self, ctx:SMILE_SpecificParser.ConstraintBodyReferenceContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#ConstraintBodyReference.
    def exitConstraintBodyReference(self, ctx:SMILE_SpecificParser.ConstraintBodyReferenceContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#ConstraintBodyCheck.
    def enterConstraintBodyCheck(self, ctx:SMILE_SpecificParser.ConstraintBodyCheckContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#ConstraintBodyCheck.
    def exitConstraintBodyCheck(self, ctx:SMILE_SpecificParser.ConstraintBodyCheckContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#ConstraintBodyExistence.
    def enterConstraintBodyExistence(self, ctx:SMILE_SpecificParser.ConstraintBodyExistenceContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#ConstraintBodyExistence.
    def exitConstraintBodyExistence(self, ctx:SMILE_SpecificParser.ConstraintBodyExistenceContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#delete_constraint.
    def enterDelete_constraint(self, ctx:SMILE_SpecificParser.Delete_constraintContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#delete_constraint.
    def exitDelete_constraint(self, ctx:SMILE_SpecificParser.Delete_constraintContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CheckParenExpr.
    def enterCheckParenExpr(self, ctx:SMILE_SpecificParser.CheckParenExprContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CheckParenExpr.
    def exitCheckParenExpr(self, ctx:SMILE_SpecificParser.CheckParenExprContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CheckAtomExpr.
    def enterCheckAtomExpr(self, ctx:SMILE_SpecificParser.CheckAtomExprContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CheckAtomExpr.
    def exitCheckAtomExpr(self, ctx:SMILE_SpecificParser.CheckAtomExprContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CheckAndExpr.
    def enterCheckAndExpr(self, ctx:SMILE_SpecificParser.CheckAndExprContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CheckAndExpr.
    def exitCheckAndExpr(self, ctx:SMILE_SpecificParser.CheckAndExprContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CheckOrExpr.
    def enterCheckOrExpr(self, ctx:SMILE_SpecificParser.CheckOrExprContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CheckOrExpr.
    def exitCheckOrExpr(self, ctx:SMILE_SpecificParser.CheckOrExprContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CheckNotExpr.
    def enterCheckNotExpr(self, ctx:SMILE_SpecificParser.CheckNotExprContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CheckNotExpr.
    def exitCheckNotExpr(self, ctx:SMILE_SpecificParser.CheckNotExprContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CheckRawExpr.
    def enterCheckRawExpr(self, ctx:SMILE_SpecificParser.CheckRawExprContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CheckRawExpr.
    def exitCheckRawExpr(self, ctx:SMILE_SpecificParser.CheckRawExprContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#CmpAtom.
    def enterCmpAtom(self, ctx:SMILE_SpecificParser.CmpAtomContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#CmpAtom.
    def exitCmpAtom(self, ctx:SMILE_SpecificParser.CmpAtomContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#InAtom.
    def enterInAtom(self, ctx:SMILE_SpecificParser.InAtomContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#InAtom.
    def exitInAtom(self, ctx:SMILE_SpecificParser.InAtomContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#BetweenAtom.
    def enterBetweenAtom(self, ctx:SMILE_SpecificParser.BetweenAtomContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#BetweenAtom.
    def exitBetweenAtom(self, ctx:SMILE_SpecificParser.BetweenAtomContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#RegexAtom.
    def enterRegexAtom(self, ctx:SMILE_SpecificParser.RegexAtomContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#RegexAtom.
    def exitRegexAtom(self, ctx:SMILE_SpecificParser.RegexAtomContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#IsNullAtom.
    def enterIsNullAtom(self, ctx:SMILE_SpecificParser.IsNullAtomContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#IsNullAtom.
    def exitIsNullAtom(self, ctx:SMILE_SpecificParser.IsNullAtomContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#IsNotNullAtom.
    def enterIsNotNullAtom(self, ctx:SMILE_SpecificParser.IsNotNullAtomContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#IsNotNullAtom.
    def exitIsNotNullAtom(self, ctx:SMILE_SpecificParser.IsNotNullAtomContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#cmpOp.
    def enterCmpOp(self, ctx:SMILE_SpecificParser.CmpOpContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#cmpOp.
    def exitCmpOp(self, ctx:SMILE_SpecificParser.CmpOpContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#literalList.
    def enterLiteralList(self, ctx:SMILE_SpecificParser.LiteralListContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#literalList.
    def exitLiteralList(self, ctx:SMILE_SpecificParser.LiteralListContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#cast_entity.
    def enterCast_entity(self, ctx:SMILE_SpecificParser.Cast_entityContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#cast_entity.
    def exitCast_entity(self, ctx:SMILE_SpecificParser.Cast_entityContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#recard.
    def enterRecard(self, ctx:SMILE_SpecificParser.RecardContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#recard.
    def exitRecard(self, ctx:SMILE_SpecificParser.RecardContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#transform.
    def enterTransform(self, ctx:SMILE_SpecificParser.TransformContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#transform.
    def exitTransform(self, ctx:SMILE_SpecificParser.TransformContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#TransformToRelationship.
    def enterTransformToRelationship(self, ctx:SMILE_SpecificParser.TransformToRelationshipContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#TransformToRelationship.
    def exitTransformToRelationship(self, ctx:SMILE_SpecificParser.TransformToRelationshipContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#TransformToEntity.
    def enterTransformToEntity(self, ctx:SMILE_SpecificParser.TransformToEntityContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#TransformToEntity.
    def exitTransformToEntity(self, ctx:SMILE_SpecificParser.TransformToEntityContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withCardinalityClause.
    def enterWithCardinalityClause(self, ctx:SMILE_SpecificParser.WithCardinalityClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withCardinalityClause.
    def exitWithCardinalityClause(self, ctx:SMILE_SpecificParser.WithCardinalityClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#usingKeyClause.
    def enterUsingKeyClause(self, ctx:SMILE_SpecificParser.UsingKeyClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#usingKeyClause.
    def exitUsingKeyClause(self, ctx:SMILE_SpecificParser.UsingKeyClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#whereClause.
    def enterWhereClause(self, ctx:SMILE_SpecificParser.WhereClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#whereClause.
    def exitWhereClause(self, ctx:SMILE_SpecificParser.WhereClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#withPropertiesClause.
    def enterWithPropertiesClause(self, ctx:SMILE_SpecificParser.WithPropertiesClauseContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#withPropertiesClause.
    def exitWithPropertiesClause(self, ctx:SMILE_SpecificParser.WithPropertiesClauseContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#propertyDefList.
    def enterPropertyDefList(self, ctx:SMILE_SpecificParser.PropertyDefListContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#propertyDefList.
    def exitPropertyDefList(self, ctx:SMILE_SpecificParser.PropertyDefListContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#propertyDef.
    def enterPropertyDef(self, ctx:SMILE_SpecificParser.PropertyDefContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#propertyDef.
    def exitPropertyDef(self, ctx:SMILE_SpecificParser.PropertyDefContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#identifierList.
    def enterIdentifierList(self, ctx:SMILE_SpecificParser.IdentifierListContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#identifierList.
    def exitIdentifierList(self, ctx:SMILE_SpecificParser.IdentifierListContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#cardinalityType.
    def enterCardinalityType(self, ctx:SMILE_SpecificParser.CardinalityTypeContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#cardinalityType.
    def exitCardinalityType(self, ctx:SMILE_SpecificParser.CardinalityTypeContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#constraintKeyType.
    def enterConstraintKeyType(self, ctx:SMILE_SpecificParser.ConstraintKeyTypeContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#constraintKeyType.
    def exitConstraintKeyType(self, ctx:SMILE_SpecificParser.ConstraintKeyTypeContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#dataType.
    def enterDataType(self, ctx:SMILE_SpecificParser.DataTypeContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#dataType.
    def exitDataType(self, ctx:SMILE_SpecificParser.DataTypeContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#qualifiedName.
    def enterQualifiedName(self, ctx:SMILE_SpecificParser.QualifiedNameContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#qualifiedName.
    def exitQualifiedName(self, ctx:SMILE_SpecificParser.QualifiedNameContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#pathSegment.
    def enterPathSegment(self, ctx:SMILE_SpecificParser.PathSegmentContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#pathSegment.
    def exitPathSegment(self, ctx:SMILE_SpecificParser.PathSegmentContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#identifier.
    def enterIdentifier(self, ctx:SMILE_SpecificParser.IdentifierContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#identifier.
    def exitIdentifier(self, ctx:SMILE_SpecificParser.IdentifierContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#condition.
    def enterCondition(self, ctx:SMILE_SpecificParser.ConditionContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#condition.
    def exitCondition(self, ctx:SMILE_SpecificParser.ConditionContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#equalityCondition.
    def enterEqualityCondition(self, ctx:SMILE_SpecificParser.EqualityConditionContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#equalityCondition.
    def exitEqualityCondition(self, ctx:SMILE_SpecificParser.EqualityConditionContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#edgeCondition.
    def enterEdgeCondition(self, ctx:SMILE_SpecificParser.EdgeConditionContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#edgeCondition.
    def exitEdgeCondition(self, ctx:SMILE_SpecificParser.EdgeConditionContext):
        pass


    # Enter a parse tree produced by SMILE_SpecificParser#literal.
    def enterLiteral(self, ctx:SMILE_SpecificParser.LiteralContext):
        pass

    # Exit a parse tree produced by SMILE_SpecificParser#literal.
    def exitLiteral(self, ctx:SMILE_SpecificParser.LiteralContext):
        pass



del SMILE_SpecificParser